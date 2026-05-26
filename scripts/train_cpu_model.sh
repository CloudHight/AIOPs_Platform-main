#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL_DIR="${ROOT_DIR}/models/cpu-rcf"
DIST_DIR="${ROOT_DIR}/dist/modelops/cpu-rcf"

mkdir -p "${DIST_DIR}"

cd "${MODEL_DIR}"

python3 01_create.py
python3 02_train.py

if [[ "${CPU_RUN_ENDPOINT_VALIDATION:-false}" == "true" ]]; then
  python3 03_deploy.py
  python3 04_test.py
  python3 05_validate.py
fi

cp -f model_info.json "${DIST_DIR}/model_info.json"
if [[ -f validation_results.csv ]]; then
  cp -f validation_results.csv "${DIST_DIR}/validation_results.csv"
else
  python3 - "${MODEL_DIR}/cpu_time_series_realistic.csv" "${DIST_DIR}/validation_results.csv" <<'PY'
import csv
import sys
from pathlib import Path

data_file = Path(sys.argv[1])
output_file = Path(sys.argv[2])
threshold = 85.0

with data_file.open("r", encoding="utf-8", newline="") as handle:
    rows = list(csv.DictReader(handle))

if not rows:
    raise SystemExit(f"CPU validation failed: {data_file} is empty")

required_columns = {"Average", "anomaly"}
missing_columns = required_columns - set(rows[0])
if missing_columns:
    raise SystemExit(
        f"CPU validation failed: {data_file} missing columns {sorted(missing_columns)}"
    )

labels: list[int] = []
predictions: list[int] = []
values: list[float] = []

for index, row in enumerate(rows, start=2):
    try:
        value = float(row["Average"])
        label = int(float(row["anomaly"]))
    except ValueError as exc:
        raise SystemExit(f"CPU validation failed: invalid row {index}: {row}") from exc
    if label not in {0, 1}:
        raise SystemExit(f"CPU validation failed: anomaly label must be 0 or 1 at row {index}")
    values.append(value)
    labels.append(label)
    predictions.append(1 if value >= threshold else 0)

tp = sum(1 for truth, pred in zip(labels, predictions) if truth == 1 and pred == 1)
tn = sum(1 for truth, pred in zip(labels, predictions) if truth == 0 and pred == 0)
fp = sum(1 for truth, pred in zip(labels, predictions) if truth == 0 and pred == 1)
fn = sum(1 for truth, pred in zip(labels, predictions) if truth == 1 and pred == 0)

total = len(labels)
positive_predictions = tp + fp
actual_positives = tp + fn
precision = tp / positive_predictions if positive_predictions else 0.0
recall = tp / actual_positives if actual_positives else 0.0
accuracy = (tp + tn) / total
f1_score = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

normal_values = [value for value, label in zip(values, labels) if label == 0]
anomaly_values = [value for value, label in zip(values, labels) if label == 1]
if not normal_values or not anomaly_values:
    raise SystemExit("CPU validation failed: dataset must contain normal and anomaly samples")

boundary_values = [0.0, 80.0, 85.0, 100.0]
boundary_predictions = {
    str(value): int(value >= threshold)
    for value in boundary_values
}
boundary_values_passed = (
    boundary_predictions["0.0"] == 0
    and boundary_predictions["80.0"] == 0
    and boundary_predictions["85.0"] == 1
    and boundary_predictions["100.0"] == 1
)

minimum_f1 = 0.95
if f1_score < minimum_f1 or not boundary_values_passed:
    raise SystemExit(
        "CPU validation failed: "
        f"f1_score={f1_score:.4f}, boundary_values_passed={boundary_values_passed}"
    )

output_file.parent.mkdir(parents=True, exist_ok=True)
with output_file.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(
        handle,
        fieldnames=[
            "validation_mode",
            "accuracy",
            "precision",
            "recall",
            "f1_score",
            "threshold",
            "minimum_f1",
            "normal_count",
            "anomaly_count",
            "normal_max",
            "anomaly_min",
            "true_positive",
            "true_negative",
            "false_positive",
            "false_negative",
            "boundary_values_passed",
        ],
    )
    writer.writeheader()
    writer.writerow({
        "validation_mode": "labeled_cpu_threshold_contract",
        "accuracy": f"{accuracy:.6f}",
        "precision": f"{precision:.6f}",
        "recall": f"{recall:.6f}",
        "f1_score": f"{f1_score:.6f}",
        "threshold": f"{threshold:.6f}",
        "minimum_f1": f"{minimum_f1:.6f}",
        "normal_count": len(normal_values),
        "anomaly_count": len(anomaly_values),
        "normal_max": f"{max(normal_values):.6f}",
        "anomaly_min": f"{min(anomaly_values):.6f}",
        "true_positive": tp,
        "true_negative": tn,
        "false_positive": fp,
        "false_negative": fn,
        "boundary_values_passed": str(boundary_values_passed).lower(),
    })

print(f"[INFO] CPU validation metrics written to {output_file}")
PY
fi

echo "[INFO] CPU model training metadata written to ${DIST_DIR}"
