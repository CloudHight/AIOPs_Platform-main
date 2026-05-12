#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL_DIR="${ROOT_DIR}/RCF_Model"
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
fi

echo "[INFO] CPU model training metadata written to ${DIST_DIR}"

