#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CPU_PUBLISHED_FILE="${ROOT_DIR}/dist/modelops/cpu-rcf-published.json"
LOG_PUBLISHED_FILE="${ROOT_DIR}/dist/modelops/nginx-bert-published.json"
ARGS=()

if [[ -f "${CPU_PUBLISHED_FILE}" ]]; then
  ARGS+=(--cpu-published-file "${CPU_PUBLISHED_FILE}")
fi

if [[ -f "${LOG_PUBLISHED_FILE}" ]]; then
  ARGS+=(--log-published-file "${LOG_PUBLISHED_FILE}")
fi

if [[ ${#ARGS[@]} -gt 0 ]]; then
  python3 "${ROOT_DIR}/scripts/modelops.py" write-tfvars \
    "${ARGS[@]}" \
    --output-file "${1:-${ROOT_DIR}/dist/modelops/model-artifacts.auto.tfvars.json}"
else
  python3 "${ROOT_DIR}/scripts/modelops.py" write-tfvars \
    --output-file "${1:-${ROOT_DIR}/dist/modelops/model-artifacts.auto.tfvars.json}"
fi
