#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

: "${MODEL_ARTIFACT_BUCKET:?MODEL_ARTIFACT_BUCKET is required}"

S3_PREFIX="${MODEL_ARTIFACT_PREFIX:-models}"

publish_one() {
  local model_name="$1"
  local handoff="${ROOT_DIR}/dist/modelops/${model_name}/handoff.json"
  if [[ ! -f "${handoff}" ]]; then
    echo "[WARN] Missing handoff file for ${model_name}: ${handoff}" >&2
    return
  fi

  python3 "${ROOT_DIR}/scripts/modelops.py" publish \
    --handoff-file "${handoff}" \
    --bucket "${MODEL_ARTIFACT_BUCKET}" \
    --s3-prefix "${S3_PREFIX}" \
    --output-dir "${ROOT_DIR}/dist/modelops"
}

case "${1:-all}" in
  cpu) publish_one cpu-rcf ;;
  log) publish_one nginx-bert ;;
  all)
    publish_one cpu-rcf
    publish_one nginx-bert
    ;;
  *)
    echo "Usage: $0 [cpu|log|all]" >&2
    exit 2
    ;;
esac

