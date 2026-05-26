#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL_DIR="${ROOT_DIR}/models/nginx-bert"
DIST_DIR="${ROOT_DIR}/dist/modelops/nginx-bert"

: "${MODEL_ARTIFACT_BUCKET:?MODEL_ARTIFACT_BUCKET is required for log model dataset upload/training}"

DATA_PREFIX="${LOG_DATA_PREFIX:-nginx-bert/data/${BUILD_NUMBER:-local}}"
WAIT_ARGS=()
if [[ "${LOG_TRAIN_WAIT:-false}" == "true" ]]; then
  WAIT_ARGS=(--wait)
fi

mkdir -p "${DIST_DIR}"

cd "${MODEL_DIR}"

python3 01_create_data.py \
  --output-dir data \
  --bucket "${MODEL_ARTIFACT_BUCKET}" \
  --s3-prefix "${DATA_PREFIX}"

python3 02_train_model.py \
  --bucket "${MODEL_ARTIFACT_BUCKET}" \
  --prefix "${DATA_PREFIX}" \
  --train-script train.py \
  --metadata-output "${DIST_DIR}/training_metadata.json" \
  "${WAIT_ARGS[@]}" | tee "${DIST_DIR}/training.log"

if [[ -s "${DIST_DIR}/training_metadata.json" ]]; then
  python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["tuning_job_name"])' \
    "${DIST_DIR}/training_metadata.json" > "${DIST_DIR}/tuning_job_name.txt"
else
  grep -Eo 'Tuning job name: [A-Za-z0-9_.-]+' "${DIST_DIR}/training.log" \
    | awk '{print $4}' \
    | tail -1 > "${DIST_DIR}/tuning_job_name.txt" || true
fi

if [[ ! -s "${DIST_DIR}/tuning_job_name.txt" ]]; then
  echo "[ERROR] Log model training completed without publishing a SageMaker tuning job name." >&2
  echo "[ERROR] Expected ${DIST_DIR}/training_metadata.json or a 'Tuning job name:' line in ${DIST_DIR}/training.log." >&2
  exit 1
fi

if [[ "${LOG_TRAIN_WAIT:-false}" == "true" ]]; then
  tuning_job_name="$(tr -d '[:space:]' < "${DIST_DIR}/tuning_job_name.txt")"
  python3 03_validate_model.py \
    --tuning-job-name "${tuning_job_name}" \
    --minimum-f1 "${LOG_MIN_F1:-0.8}" \
    --output-file "${DIST_DIR}/evaluation_metrics.json" | tee "${DIST_DIR}/validation.log"

  if [[ ! -s "${DIST_DIR}/evaluation_metrics.json" ]]; then
    echo "[ERROR] Log model validation did not publish ${DIST_DIR}/evaluation_metrics.json." >&2
    exit 1
  fi
else
  echo "[WARN] LOG_TRAIN_WAIT is not true; skipping log model evaluation metrics export." >&2
fi

echo "[INFO] Log model training metadata written to ${DIST_DIR}"
