#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: scripts/recover_kms_key.sh <key-arn|key-id|alias/name> <dev|stage|prod>

Cancels deletion for a recoverable KMS key, enables it if disabled, and ensures
alias/aiops-<env> points to that key. Use this only when the old key is still
the correct key for the environment.
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -ne 2 ]]; then
  usage >&2
  exit 2
fi

key_id="$1"
environment="$2"

case "${environment}" in
  dev | stage | prod) ;;
  *)
    printf 'KMS recovery failed: unsupported environment "%s".\n' "${environment}" >&2
    exit 2
    ;;
esac

for required in aws jq; do
  if ! command -v "${required}" >/dev/null 2>&1; then
    printf 'KMS recovery failed: required command not found: %s\n' "${required}" >&2
    exit 2
  fi
done

key_json="$(aws kms describe-key --key-id "${key_id}")"
state="$(printf '%s' "${key_json}" | jq -r '.KeyMetadata.KeyState')"
target_key_id="$(printf '%s' "${key_json}" | jq -r '.KeyMetadata.KeyId')"
target_key_arn="$(printf '%s' "${key_json}" | jq -r '.KeyMetadata.Arn')"
alias_name="alias/aiops-${environment}"

if [[ "${state}" == "PendingDeletion" ]]; then
  aws kms cancel-key-deletion --key-id "${target_key_id}" >/dev/null
  state="Disabled"
  printf 'Cancelled deletion for KMS key: %s\n' "${target_key_arn}"
fi

if [[ "${state}" == "Disabled" ]]; then
  aws kms enable-key --key-id "${target_key_id}"
  printf 'Enabled KMS key: %s\n' "${target_key_arn}"
fi

if aws kms describe-key --key-id "${alias_name}" >/dev/null 2>&1; then
  aws kms update-alias --alias-name "${alias_name}" --target-key-id "${target_key_id}"
  printf 'Updated %s -> %s\n' "${alias_name}" "${target_key_arn}"
else
  aws kms create-alias --alias-name "${alias_name}" --target-key-id "${target_key_id}"
  printf 'Created %s -> %s\n' "${alias_name}" "${target_key_arn}"
fi

aws kms describe-key --key-id "${alias_name}" \
  --query 'KeyMetadata.{Arn:Arn,KeyState:KeyState,Enabled:Enabled}' \
  --output table
