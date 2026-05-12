#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

find "${ROOT_DIR}" -type d -name __pycache__ -prune -exec rm -rf {} +
find "${ROOT_DIR}" -type f -name '*.pyc' -delete
find "${ROOT_DIR}/infra/envs" -type f \( -name 'jenkins.auto.tfvars' -o -name 'tfplan' \) -delete

printf 'Cleaned generated Python caches and transient Terraform plan files.\n'
