import argparse
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import accuracy_score, f1_score, precision_recall_curve, precision_score, recall_score
from torch import nn
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    EarlyStoppingCallback,
    Trainer,
    TrainingArguments,
)


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--per_device_train_batch_size", type=int, default=16)
    parser.add_argument("--per_device_eval_batch_size", type=int, default=32)
    parser.add_argument("--learning_rate", type=float, default=2e-5)
    parser.add_argument("--weight_decay", type=float, default=0.01)
    parser.add_argument("--max_seq_length", type=int, default=192)
    parser.add_argument("--model_name", type=str, default="distilbert-base-uncased")
    parser.add_argument("--num_labels", type=int, default=2)
    parser.add_argument("--threshold_objective", type=str, default="f1", choices=["f1", "precision", "recall"])
    parser.add_argument("--output_data_dir", type=str, default=os.environ.get("SM_OUTPUT_DATA_DIR", "./outputs"))
    parser.add_argument("--model_dir", type=str, default=os.environ.get("SM_MODEL_DIR", "./model"))
    parser.add_argument("--train_data", type=str, default=os.environ.get("SM_CHANNEL_TRAIN", "./data/train"))
    parser.add_argument("--validation_data", type=str, default=os.environ.get("SM_CHANNEL_VALIDATION", "./data/validation"))
    parser.add_argument("--test_data", type=str, default=os.environ.get("SM_CHANNEL_TEST", "./data/test"))
    parser.add_argument("--fp16", action="store_true")
    parser.add_argument("--bf16", action="store_true")
    return parser.parse_args()


def normalize_text(text: str) -> str:
    text = str(text).strip()
    text = re.sub(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", "<IP>", text)
    text = re.sub(r"\[\d{2}/[A-Za-z]{3}/\d{4}:\d{2}:\d{2}:\d{2} \+\d{4}\]", "[<TIME>]", text)
    text = re.sub(r"\b\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}\b", "<TIME>", text)
    text = re.sub(r"req_id=[A-Fa-f0-9]+", "req_id=<ID>", text)
    text = re.sub(r"\b[A-Fa-f0-9]{8,32}\b", "<ID>", text)
    text = re.sub(r"\b\d+\.\d+\b", "<FLOAT>", text)
    text = re.sub(r"\b\d+\b", "<NUM>", text)
    return re.sub(r"\s+", " ", text).strip()


def load_dataset(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Data path not found: {path}")

    files = [Path(path)] if os.path.isfile(path) else sorted(Path(path).glob("*.json"))
    records: List[Dict[str, Any]] = []
    for file_path in files:
        with file_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if isinstance(payload, list):
            records.extend(payload)
        elif isinstance(payload, dict):
            records.append(payload)

    df = pd.DataFrame(records)
    if df.empty:
        raise ValueError(f"No records loaded from {path}")

    df["text"] = df["text"].astype(str).map(normalize_text)
    df["label"] = df["label"].astype(int)
    if "difficulty" not in df:
        df["difficulty"] = "unknown"
    logger.info("Loaded %s rows from %s", len(df), path)
    return df


class LogDataset(torch.utils.data.Dataset):
    def __init__(self, encodings: Dict[str, np.ndarray], labels: np.ndarray):
        self.encodings = encodings
        self.labels = labels

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        item = {key: torch.tensor(value[idx], dtype=torch.long) for key, value in self.encodings.items()}
        item["labels"] = torch.tensor(int(self.labels[idx]), dtype=torch.long)
        return item

    def __len__(self) -> int:
        return len(self.labels)


class WeightedTrainer(Trainer):
    def __init__(self, class_weights: torch.Tensor, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.class_weights = class_weights

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        labels = inputs.pop("labels")
        outputs = model(**inputs)
        logits = outputs.get("logits")
        loss_fn = nn.CrossEntropyLoss(weight=self.class_weights.to(logits.device))
        loss = loss_fn(logits.view(-1, model.config.num_labels), labels.view(-1))
        return (loss, outputs) if return_outputs else loss


def compute_metrics(eval_pred: Tuple[np.ndarray, np.ndarray]) -> Dict[str, float]:
    logits, labels = eval_pred
    preds = logits.argmax(axis=-1)
    return {
        "eval_f1_macro": f1_score(labels, preds, average="macro"),
        "eval_f1_anomaly": f1_score(labels, preds, pos_label=1),
        "eval_precision": precision_score(labels, preds, zero_division=0),
        "eval_recall": recall_score(labels, preds, zero_division=0),
        "eval_accuracy": accuracy_score(labels, preds),
    }


def pick_threshold(labels: np.ndarray, anomaly_probs: np.ndarray, objective: str) -> Dict[str, float]:
    precisions, recalls, thresholds = precision_recall_curve(labels, anomaly_probs)
    candidates: List[Dict[str, float]] = []
    for idx, threshold in enumerate(thresholds):
        precision = float(precisions[idx])
        recall = float(recalls[idx])
        f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
        candidates.append(
            {
                "threshold": float(threshold),
                "precision": precision,
                "recall": recall,
                "f1": f1,
            }
        )

    if not candidates:
        return {"threshold": 0.5, "precision": 0.0, "recall": 0.0, "f1": 0.0}

    key = {"f1": "f1", "precision": "precision", "recall": "recall"}[objective]
    best = max(candidates, key=lambda item: (item[key], item["f1"], item["precision"]))
    return best


def save_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def main() -> None:
    args = parse_args()

    if args.fp16 and args.bf16:
        raise ValueError("Only one of fp16 or bf16 can be enabled.")
    if not args.fp16 and not args.bf16 and torch.cuda.is_available():
        args.bf16 = torch.cuda.get_device_capability()[0] >= 8
        args.fp16 = not args.bf16

    train_df = load_dataset(args.train_data)
    val_df = load_dataset(args.validation_data)
    test_df = load_dataset(args.test_data) if os.path.exists(args.test_data) else None

    tokenizer = AutoTokenizer.from_pretrained(args.model_name)

    def tokenize(texts: List[str]) -> Dict[str, np.ndarray]:
        return tokenizer(
            texts,
            padding="max_length",
            truncation=True,
            max_length=args.max_seq_length,
            return_tensors="np",
        )

    train_ds = LogDataset(tokenize(train_df["text"].tolist()), train_df["label"].values)
    val_ds = LogDataset(tokenize(val_df["text"].tolist()), val_df["label"].values)
    test_ds = LogDataset(tokenize(test_df["text"].tolist()), test_df["label"].values) if test_df is not None else None

    label_counts = train_df["label"].value_counts().sort_index()
    total = int(label_counts.sum())
    class_weights = torch.tensor(
        [total / (len(label_counts) * max(1, int(label_counts.get(i, 1)))) for i in range(args.num_labels)],
        dtype=torch.float,
    )
    logger.info("Class weights: %s", class_weights.tolist())

    model = AutoModelForSequenceClassification.from_pretrained(args.model_name, num_labels=args.num_labels)

    training_args = TrainingArguments(
        output_dir=args.model_dir,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        learning_rate=args.learning_rate,
        per_device_train_batch_size=args.per_device_train_batch_size,
        per_device_eval_batch_size=args.per_device_eval_batch_size,
        num_train_epochs=args.epochs,
        weight_decay=args.weight_decay,
        load_best_model_at_end=True,
        metric_for_best_model="eval_f1_anomaly",
        greater_is_better=True,
        logging_dir=os.path.join(args.output_data_dir, "logs"),
        logging_steps=20,
        report_to="none",
        fp16=args.fp16,
        bf16=args.bf16,
        no_cuda=not torch.cuda.is_available(),
        save_total_limit=2,
        seed=42,
    )

    trainer = WeightedTrainer(
        class_weights=class_weights,
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        compute_metrics=compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=2)],
    )

    train_result = trainer.train()
    trainer.save_model(args.model_dir)
    tokenizer.save_pretrained(args.model_dir)

    logger.info("Training metrics: %s", train_result.metrics)
    validation_metrics = trainer.evaluate(eval_dataset=val_ds)
    logger.info("Validation metrics: %s", validation_metrics)

    val_predictions = trainer.predict(val_ds)
    val_probs = torch.softmax(torch.tensor(val_predictions.predictions), dim=-1).numpy()[:, 1]
    threshold_info = pick_threshold(val_predictions.label_ids, val_probs, args.threshold_objective)

    metrics_payload: Dict[str, Any] = {
        "train_metrics": train_result.metrics,
        "validation_metrics": validation_metrics,
        "threshold_config": threshold_info,
        "class_weights": class_weights.tolist(),
        "model_name": args.model_name,
        "max_seq_length": args.max_seq_length,
    }

    if test_ds is not None:
        test_predictions = trainer.predict(test_ds)
        test_probs = torch.softmax(torch.tensor(test_predictions.predictions), dim=-1).numpy()[:, 1]
        threshold = threshold_info["threshold"]
        test_preds = (test_probs >= threshold).astype(int)
        metrics_payload["test_metrics"] = {
            "f1": f1_score(test_predictions.label_ids, test_preds, zero_division=0),
            "precision": precision_score(test_predictions.label_ids, test_preds, zero_division=0),
            "recall": recall_score(test_predictions.label_ids, test_preds, zero_division=0),
            "accuracy": accuracy_score(test_predictions.label_ids, test_preds),
        }

    save_json(Path(args.model_dir) / "training_summary.json", metrics_payload)
    save_json(Path(args.model_dir) / "threshold_config.json", threshold_info)

    print(f"'best_threshold': {threshold_info['threshold']}")
    print(f"'threshold_f1': {threshold_info['f1']}")
    print(f"'threshold_precision': {threshold_info['precision']}")
    print(f"'threshold_recall': {threshold_info['recall']}")


if __name__ == "__main__":
    main()
