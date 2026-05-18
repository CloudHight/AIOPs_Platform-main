#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 <model-version> <output-file>" >&2
  exit 2
fi

MODEL_VERSION="$1"
OUTPUT_FILE="$2"

: "${MODEL_ARTIFACT_BUCKET:?MODEL_ARTIFACT_BUCKET is required}"
: "${CPU_MODEL_IMAGE_URI:?CPU_MODEL_IMAGE_URI is required}"
: "${LOG_MODEL_IMAGE_URI:?LOG_MODEL_IMAGE_URI is required}"

if [[ -z "${MODEL_VERSION}" ]]; then
  echo "Model version is required when using existing model artifacts." >&2
  exit 1
fi

if [[ ! "${MODEL_VERSION}" =~ ^[A-Za-z0-9_.-]+$ ]]; then
  echo "Model version may only contain letters, numbers, dots, underscores, and hyphens." >&2
  exit 1
fi

for model_name in cpu-rcf nginx-bert; do
  for artifact_name in model.tar.gz metadata.json evaluation.json; do
    key="models/${model_name}/${MODEL_VERSION}/${artifact_name}"
    aws s3api head-object \
      --bucket "${MODEL_ARTIFACT_BUCKET}" \
      --key "${key}" \
      >/dev/null
  done
done

mkdir -p "$(dirname "${OUTPUT_FILE}")"

jq -n \
  --arg model_version "${MODEL_VERSION}" \
  --arg bucket "${MODEL_ARTIFACT_BUCKET}" \
  --arg cpu_image_uri "${CPU_MODEL_IMAGE_URI}" \
  --arg log_image_uri "${LOG_MODEL_IMAGE_URI}" \
  '{
    model_version: $model_version,
    cpu_model_artifact_s3_uri: "s3://\($bucket)/models/cpu-rcf/\($model_version)/model.tar.gz",
    log_model_artifact_s3_uri: "s3://\($bucket)/models/nginx-bert/\($model_version)/model.tar.gz",
    cpu_model_image_uri: $cpu_image_uri,
    log_model_image_uri: $log_image_uri
  }' > "${OUTPUT_FILE}"

echo "[INFO] Wrote existing model Terraform vars to ${OUTPUT_FILE}"
