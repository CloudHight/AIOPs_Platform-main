#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL_ROOT="${ROOT_DIR}/dist/modelops"

python3 - "$MODEL_ROOT" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
required = {
    "cpu-rcf": "text/csv",
    "nginx-bert": "application/json",
}

errors: list[str] = []

for model_name, expected_content_type in required.items():
    model_dir = root / model_name
    metadata_path = model_dir / "metadata.json"
    evaluation_path = model_dir / "evaluation.json"
    handoff_path = model_dir / "handoff.json"

    for path in (metadata_path, evaluation_path, handoff_path):
        if not path.is_file():
            errors.append(f"{model_name}: missing {path}")

    if not metadata_path.is_file() or not evaluation_path.is_file() or not handoff_path.is_file():
        continue

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
    handoff = json.loads(handoff_path.read_text(encoding="utf-8"))

    if metadata.get("model_name") != model_name:
        errors.append(f"{model_name}: metadata model_name mismatch")
    if not metadata.get("model_version"):
        errors.append(f"{model_name}: missing model_version")
    if not metadata.get("git_commit"):
        errors.append(f"{model_name}: missing git_commit")
    if not metadata.get("jenkins_build_number"):
        errors.append(f"{model_name}: missing jenkins_build_number")
    if not metadata.get("container_image_uri"):
        errors.append(f"{model_name}: missing container_image_uri")

    contract = metadata.get("inference_contract") or {}
    if contract.get("content_type") != expected_content_type:
        errors.append(f"{model_name}: expected content_type {expected_content_type}")
    if not contract.get("response_shape"):
        errors.append(f"{model_name}: missing response_shape")

    if not (handoff.get("source_model_artifact_s3_uri") or handoff.get("local_model_artifact")):
        errors.append(f"{model_name}: handoff has no source model artifact")

    if evaluation.get("model_name") != model_name:
        errors.append(f"{model_name}: evaluation model_name mismatch")
    if "inference_contract" not in evaluation:
        errors.append(f"{model_name}: evaluation missing inference_contract")
    if not evaluation.get("metrics"):
        errors.append(f"{model_name}: evaluation metrics are empty")
    if (evaluation.get("thresholds") or {}).get("anomaly_score_threshold") is None:
        errors.append(f"{model_name}: evaluation missing anomaly_score_threshold")

if errors:
    print("Model handoff validation failed:", file=sys.stderr)
    for error in errors:
        print(f"- {error}", file=sys.stderr)
    sys.exit(1)

print("Model handoff validation passed.")
PY
