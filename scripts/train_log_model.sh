#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL_DIR="${ROOT_DIR}/BERT_Model"
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
  "${WAIT_ARGS[@]}" | tee "${DIST_DIR}/training.log"

grep -Eo 'hf-nginx-anomaly-update-[A-Za-z0-9-]+' "${DIST_DIR}/training.log" | tail -1 > "${DIST_DIR}/tuning_job_name.txt" || true

echo "[INFO] Log model training metadata written to ${DIST_DIR}"

