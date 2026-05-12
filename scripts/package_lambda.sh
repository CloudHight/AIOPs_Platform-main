#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${ROOT_DIR}/dist/lambda/build"
PACKAGE_DIR="${BUILD_DIR}/package"
ZIP_PATH="${ROOT_DIR}/dist/lambda/aiops-lambda.zip"
PYTHON_BIN="${AIOPS_PYTHON:-python3.12}"

rm -rf "${BUILD_DIR}" "${ZIP_PATH}" "${ZIP_PATH}.sha256" "${ZIP_PATH}.base64sha256"
mkdir -p "${PACKAGE_DIR}"

if [[ -s "${ROOT_DIR}/lambda/requirements.txt" ]]; then
  "${PYTHON_BIN}" -m pip install \
    --requirement "${ROOT_DIR}/lambda/requirements.txt" \
    --target "${PACKAGE_DIR}" \
    --upgrade
fi

cp -R "${ROOT_DIR}/lambda/src/aiops" "${PACKAGE_DIR}/aiops"
find "${PACKAGE_DIR}" -type d -name __pycache__ -prune -exec rm -rf {} +
find "${PACKAGE_DIR}" -type f -name '*.pyc' -delete
find "${PACKAGE_DIR}" -exec touch -t 200001010000 {} +

mkdir -p "$(dirname "${ZIP_PATH}")"
(
  cd "${PACKAGE_DIR}"
  find . -type f | LC_ALL=C sort | zip -X -q "${ZIP_PATH}" -@
)

if command -v sha256sum >/dev/null 2>&1; then
  sha256sum "${ZIP_PATH}" | awk '{print $1}' > "${ZIP_PATH}.sha256"
elif command -v shasum >/dev/null 2>&1; then
  shasum -a 256 "${ZIP_PATH}" | awk '{print $1}' > "${ZIP_PATH}.sha256"
else
  echo "sha256sum or shasum is required to create ${ZIP_PATH}.sha256" >&2
  exit 1
fi

openssl dgst -sha256 -binary "${ZIP_PATH}" | openssl base64 -A > "${ZIP_PATH}.base64sha256"

printf 'Packaged Lambda artifact: %s\n' "${ZIP_PATH}"
