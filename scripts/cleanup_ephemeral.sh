#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

find "${ROOT_DIR}" -type d -name __pycache__ -prune -exec rm -rf {} +
find "${ROOT_DIR}" -type d \( \
  -name .mypy_cache -o \
  -name .pytest_cache -o \
  -name .ruff_cache \
\) -prune -exec rm -rf {} +
find "${ROOT_DIR}" -type f -name '*.pyc' -delete
find "${ROOT_DIR}/infra" -type f \( \
  -name 'jenkins.auto.tfvars' -o \
  -name 'jenkins.auto.tfvars.json' -o \
  -name 'tfplan' -o \
  -name 'tfplan.txt' -o \
  -name 'tfplan.json' -o \
  -name 'destroy.tfplan' -o \
  -name 'destroy.tfplan.txt' \
\) -delete
rm -rf "${ROOT_DIR}/dist" "${ROOT_DIR}/reports"

printf 'Cleaned generated caches, reports, build artifacts, and transient Terraform files.\n'
