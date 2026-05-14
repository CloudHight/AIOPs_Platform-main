#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL_VERSION="${MODEL_VERSION:-${GIT_COMMIT:-${BUILD_NUMBER:-local}}}"

package_cpu() {
  local training_job_name="${CPU_TRAINING_JOB_NAME:-}"
  if [[ -z "${training_job_name}" && -f "${ROOT_DIR}/dist/modelops/cpu-rcf/model_info.json" ]]; then
    training_job_name="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["training_job_name"])' "${ROOT_DIR}/dist/modelops/cpu-rcf/model_info.json" 2>/dev/null || true)"
  fi

  python3 "${ROOT_DIR}/scripts/modelops.py" package \
    --model-name cpu-rcf \
    --model-version "${MODEL_VERSION}" \
    --container-image-uri "${CPU_MODEL_IMAGE_URI:?CPU_MODEL_IMAGE_URI is required}" \
    --content-type "text/csv" \
    --response-shape '{"scores":[{"score":0.0}]}' \
    --training-job-name "${training_job_name}" \
    --model-artifact-s3-uri "${CPU_MODEL_ARTIFACT_S3_URI:-}" \
    --local-model-artifact "${CPU_LOCAL_MODEL_ARTIFACT:-}" \
    --evaluation-file "${CPU_EVALUATION_FILE:-${ROOT_DIR}/dist/modelops/cpu-rcf/validation_results.csv}" \
    --threshold "${CPU_ANOMALY_THRESHOLD:-}" \
    --training-data-version "${CPU_TRAINING_DATA_VERSION:-synthetic-cpu-v1}" \
    --output-dir "${ROOT_DIR}/dist/modelops"
}

package_log() {
  local tuning_job_name="${LOG_TUNING_JOB_NAME:-}"
  local training_job_name="${LOG_TRAINING_JOB_NAME:-}"
  local artifact_s3_uri="${LOG_MODEL_ARTIFACT_S3_URI:-}"
  local local_model_artifact="${LOG_LOCAL_MODEL_ARTIFACT:-}"

  if [[ -z "${tuning_job_name}" && -f "${ROOT_DIR}/dist/modelops/nginx-bert/tuning_job_name.txt" ]]; then
    tuning_job_name="$(tr -d '[:space:]' < "${ROOT_DIR}/dist/modelops/nginx-bert/tuning_job_name.txt")"
  fi
  if [[ -z "${tuning_job_name}" && -f "${ROOT_DIR}/dist/modelops/nginx-bert/training_metadata.json" ]]; then
    tuning_job_name="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8")).get("tuning_job_name", ""))' "${ROOT_DIR}/dist/modelops/nginx-bert/training_metadata.json" 2>/dev/null || true)"
  fi

  if [[ -z "${tuning_job_name}" && -z "${training_job_name}" && -z "${artifact_s3_uri}" && -z "${local_model_artifact}" ]]; then
    echo "[ERROR] Cannot package nginx-bert model: no tuning job, training job, S3 artifact URI, or local artifact was provided." >&2
    echo "[ERROR] Run scripts/train_log_model.sh successfully, or set LOG_TUNING_JOB_NAME, LOG_TRAINING_JOB_NAME, LOG_MODEL_ARTIFACT_S3_URI, or LOG_LOCAL_MODEL_ARTIFACT." >&2
    exit 1
  fi

  python3 "${ROOT_DIR}/scripts/modelops.py" package \
    --model-name nginx-bert \
    --model-version "${MODEL_VERSION}" \
    --container-image-uri "${LOG_MODEL_IMAGE_URI:?LOG_MODEL_IMAGE_URI is required}" \
    --content-type "application/json" \
    --response-shape '[{"label":"LABEL_0","score":0.0,"threshold":0.5}]' \
    --tuning-job-name "${tuning_job_name}" \
    --training-job-name "${training_job_name}" \
    --model-artifact-s3-uri "${artifact_s3_uri}" \
    --local-model-artifact "${local_model_artifact}" \
    --evaluation-file "${LOG_EVALUATION_FILE:-}" \
    --threshold "${LOG_ANOMALY_THRESHOLD:-}" \
    --training-data-version "${LOG_TRAINING_DATA_VERSION:-synthetic-nginx-v1}" \
    --output-dir "${ROOT_DIR}/dist/modelops"
}

case "${1:-all}" in
  cpu) package_cpu ;;
  log) package_log ;;
  all)
    package_cpu
    package_log
    ;;
  *)
    echo "Usage: $0 [cpu|log|all]" >&2
    exit 2
    ;;
esac
