#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_DIR="${ROOT_DIR}/reports"
mkdir -p "${REPORT_DIR}"

if command -v gitleaks >/dev/null 2>&1; then
  gitleaks detect \
    --source "${ROOT_DIR}" \
    --no-git \
    --redact \
    --report-format json \
    --report-path "${REPORT_DIR}/gitleaks.json"
  exit 0
fi

SCAN_OUTPUT="${REPORT_DIR}/secret-scan.txt"
PATTERN='(AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|aws_secret_access_key[[:space:]]*=|-----BEGIN (RSA|OPENSSH|PRIVATE) KEY-----)'

if rg --hidden --glob '!dist/**' --glob '!reports/**' --glob '!.terraform/**' --glob '!*.tfstate*' --glob '!jenkins-pipeline-logs' --glob '!logs' -n "${PATTERN}" "${ROOT_DIR}" >"${SCAN_OUTPUT}"; then
  echo "Potential secrets found. Review ${SCAN_OUTPUT}." >&2
  cat "${SCAN_OUTPUT}" >&2
  exit 1
fi

printf 'No high-confidence secret patterns found.\n' >"${SCAN_OUTPUT}"
