import json
import os
import re
from typing import Any, Dict, List, Union

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer


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


def model_fn(model_dir: str) -> Dict[str, Any]:
    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    model = AutoModelForSequenceClassification.from_pretrained(model_dir)
    threshold = 0.5
    threshold_path = os.path.join(model_dir, "threshold_config.json")
    if os.path.exists(threshold_path):
        with open(threshold_path, "r", encoding="utf-8") as handle:
            threshold = float(json.load(handle).get("threshold", 0.5))

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model.eval()
    return {
        "tokenizer": tokenizer,
        "model": model,
        "threshold": threshold,
        "device": device,
    }


def input_fn(request_body: Union[str, bytes], request_content_type: str) -> List[str]:
    if request_content_type != "application/json":
        raise ValueError(f"Unsupported content type: {request_content_type}")

    if isinstance(request_body, bytes):
        request_body = request_body.decode("utf-8")
    payload = json.loads(request_body)

    inputs = payload.get("inputs", payload)
    if isinstance(inputs, str):
        return [normalize_text(inputs)]
    if isinstance(inputs, list):
        return [normalize_text(item) for item in inputs]
    raise ValueError("Payload must contain 'inputs' as a string or list of strings.")


def predict_fn(inputs: List[str], model_assets: Dict[str, Any]) -> List[Dict[str, Any]]:
    tokenizer = model_assets["tokenizer"]
    model = model_assets["model"]
    threshold = model_assets["threshold"]
    device = model_assets["device"]

    encoded = tokenizer(
        inputs,
        padding=True,
        truncation=True,
        max_length=192,
        return_tensors="pt",
    )
    encoded = {key: value.to(device) for key, value in encoded.items()}

    with torch.no_grad():
        logits = model(**encoded).logits
        probs = torch.softmax(logits, dim=-1)[:, 1].tolist()

    results = []
    for score in probs:
        label = "LABEL_1" if score >= threshold else "LABEL_0"
        results.append(
            {
                "label": label,
                "score": float(score),
                "threshold": float(threshold),
            }
        )
    return results


def output_fn(prediction: List[Dict[str, Any]], accept: str) -> str:
    if accept not in ("application/json", "*/*"):
        raise ValueError(f"Unsupported accept type: {accept}")
    return json.dumps(prediction)
