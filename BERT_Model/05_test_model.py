import argparse
import json
import re
from pathlib import Path
from typing import List

import boto3


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", default="model")
    parser.add_argument("--endpoint-name", default="")
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


def load_threshold(model_dir: Path) -> float:
    threshold_file = model_dir / "threshold_config.json"
    if not threshold_file.exists():
        return 0.5
    with threshold_file.open("r", encoding="utf-8") as handle:
        return float(json.load(handle).get("threshold", 0.5))


def test_local(model_dir: Path, samples: List[str]) -> None:
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    model = AutoModelForSequenceClassification.from_pretrained(model_dir)
    threshold = load_threshold(model_dir)

    inputs = tokenizer(
        [normalize_text(sample) for sample in samples],
        padding=True,
        truncation=True,
        max_length=192,
        return_tensors="pt",
    )
    with torch.no_grad():
        probs = torch.softmax(model(**inputs).logits, dim=-1)[:, 1].tolist()

    print(f"[INFO] Using threshold: {threshold}")
    for idx, (sample, score) in enumerate(zip(samples, probs), start=1):
        label = "LABEL_1" if score >= threshold else "LABEL_0"
        print(f"  Sample {idx}: {label} (anomaly_score: {score:.4f}) :: {sample}")


def test_endpoint(endpoint_name: str, samples: List[str]) -> None:
    runtime = boto3.client("sagemaker-runtime")
    print(f"[INFO] Testing endpoint: {endpoint_name}")
    for idx, sample in enumerate(samples, start=1):
        response = runtime.invoke_endpoint(
            EndpointName=endpoint_name,
            ContentType="application/json",
            Body=json.dumps({"inputs": normalize_text(sample)}),
        )
        result = json.loads(response["Body"].read().decode())
        print(f"  Sample {idx}: {result}")


if __name__ == "__main__":
    args = parse_args()
    samples = [
        '192.168.0.10 - - [16/Mar/2026:09:01:11 +0000] "GET /health HTTP/1.1" 200 532 "-" "ELB-HealthChecker/2.0" rt=0.012 req_id=a1b2c3d4e5f67890',
        '192.168.0.11 - - [16/Mar/2026:09:04:11 +0000] "POST /api/payments HTTP/1.1" 503 0 "-" "Mozilla/5.0" rt=3.428 req_id=beadbeadbeadbead',
        "2026/03/16 09:04:12 [crit] [client 10.2.3.4] no live upstreams while connecting to upstream request_id=deadbeefdeadbeef",
        '192.168.1.1 - - [01/Jan/2024:12:00:00 +0000] "GET /index.html HTTP/1.1" 200 1234',
        '192.168.1.2 - - [01/Jan/2024:12:01:00 +0000] "GET /api/data HTTP/1.1" 500 0',
        '2024/01/01 12:02:00 [error] [client 192.168.1.3] upstream server temporarily disabled',
        '192.168.1.4 - - [01/Jan/2024:12:03:00 +0000] "POST /login HTTP/1.1" 200 567',
        '2024/01/01 12:04:00 [crit] [client 192.168.1.5] no live upstreams while connecting',
    ]

    if args.endpoint_name:
        test_endpoint(args.endpoint_name, samples)
    else:
        test_local(Path(args.model_dir), samples)
