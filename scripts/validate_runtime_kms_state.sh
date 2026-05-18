#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: scripts/validate_runtime_kms_state.sh <dev|stage|prod>

Validates existing AIOps runtime SSM parameters before Terraform refresh/plan.
The script fails fast when an existing SecureString parameter is encrypted by a
KMS key that is disabled, pending deletion, or cannot decrypt the parameter.

This script is read-only. Use repair_ssm_runtime_parameters.sh for explicit
manual cleanup of obsolete broken parameters.
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -ne 1 ]]; then
  usage >&2
  exit 2
fi

environment="$1"
case "${environment}" in
  dev | stage | prod) ;;
  *)
    printf 'Runtime KMS validation failed: unsupported environment "%s".\n' "${environment}" >&2
    exit 2
    ;;
esac

for required in aws jq; do
  if ! command -v "${required}" >/dev/null 2>&1; then
    printf 'Runtime KMS validation failed: required command not found: %s\n' "${required}" >&2
    exit 2
  fi
done

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "${root_dir}/reports"
report_path="${root_dir}/reports/runtime-kms-${environment}.txt"
parameter_prefix="/AnomalyDetection/${environment}"
expected_alias="alias/aiops-${environment}"

parameter_names=(
  "${parameter_prefix}/AutoRemediationEnabled"
  "${parameter_prefix}/DryRun"
  "${parameter_prefix}/GracePeriodMinutes"
  "${parameter_prefix}/CpuThreshold"
  "${parameter_prefix}/LogThreshold"
  "${parameter_prefix}/MaxRemediationAttempts"
  "${parameter_prefix}/RemediationCooldownMinutes"
)

failures=0

{
  printf 'Runtime KMS validation\n'
  printf 'Environment: %s\n' "${environment}"
  printf 'Expected KMS alias: %s\n' "${expected_alias}"
  printf 'Parameter prefix: %s\n' "${parameter_prefix}"
} > "${report_path}"

if alias_json="$(aws kms describe-key --key-id "${expected_alias}" 2>/dev/null)"; then
  alias_key_arn="$(printf '%s' "${alias_json}" | jq -r '.KeyMetadata.Arn')"
  alias_key_state="$(printf '%s' "${alias_json}" | jq -r '.KeyMetadata.KeyState')"
  {
    printf 'Alias target key: %s\n' "${alias_key_arn}"
    printf 'Alias target state: %s\n' "${alias_key_state}"
  } >> "${report_path}"

  if [[ "${alias_key_state}" != "Enabled" ]]; then
    printf 'Runtime KMS validation failed: %s resolves to key state %s.\n' "${expected_alias}" "${alias_key_state}" >&2
    failures=$((failures + 1))
  fi
else
  printf 'Expected KMS alias not found yet: %s. Terraform may create it on first apply.\n' "${expected_alias}" >> "${report_path}"
fi

for name in "${parameter_names[@]}"; do
  parameter_json="$(
    aws ssm describe-parameters \
      --parameter-filters "Key=Name,Option=BeginsWith,Values=${name}" \
      --output json |
      jq --arg name "${name}" '{Parameters: [.Parameters[] | select(.Name == $name)]}'
  )"
  parameter_count="$(printf '%s' "${parameter_json}" | jq '.Parameters | length')"

  if [[ "${parameter_count}" -eq 0 ]]; then
    printf 'Parameter absent, Terraform can create it: %s\n' "${name}" >> "${report_path}"
    continue
  fi

  parameter_type="$(printf '%s' "${parameter_json}" | jq -r '.Parameters[0].Type')"
  key_id="$(printf '%s' "${parameter_json}" | jq -r '.Parameters[0].KeyId // ""')"

  {
    printf 'Parameter: %s\n' "${name}"
    printf '  Type: %s\n' "${parameter_type}"
    printf '  KeyId: %s\n' "${key_id:-none}"
  } >> "${report_path}"

  if [[ "${parameter_type}" != "SecureString" ]]; then
    continue
  fi

  if [[ -z "${key_id}" ]]; then
    printf 'Runtime KMS validation failed: SecureString parameter has no KeyId: %s\n' "${name}" >&2
    failures=$((failures + 1))
    continue
  fi

  if key_json="$(aws kms describe-key --key-id "${key_id}" 2>/dev/null)"; then
    key_state="$(printf '%s' "${key_json}" | jq -r '.KeyMetadata.KeyState')"
    printf '  KeyState: %s\n' "${key_state}" >> "${report_path}"
    if [[ "${key_state}" != "Enabled" ]]; then
      printf 'Runtime KMS validation failed: %s is encrypted with %s, state=%s.\n' "${name}" "${key_id}" "${key_state}" >&2
      failures=$((failures + 1))
      continue
    fi
  else
    printf 'Runtime KMS validation failed: cannot describe KMS key for %s: %s\n' "${name}" "${key_id}" >&2
    failures=$((failures + 1))
    continue
  fi

  if ! decrypt_output="$(aws ssm get-parameter --name "${name}" --with-decryption --query 'Parameter.Name' --output text 2>&1)"; then
    printf 'Runtime KMS validation failed: cannot decrypt %s: %s\n' "${name}" "${decrypt_output}" >&2
    failures=$((failures + 1))
  else
    printf '  Decryption: passed\n' >> "${report_path}"
  fi
done

if [[ "${failures}" -gt 0 ]]; then
  cat >&2 <<EOF

Runtime KMS validation found ${failures} problem(s). Terraform plan would fail while refreshing
existing SSM SecureString parameters.

If the old key is still the correct environment key, recover it and repoint the alias:
  scripts/recover_kms_key.sh <key-arn-or-key-id> ${environment}

If the old key is obsolete and these parameters should be recreated by Terraform:
  scripts/repair_ssm_runtime_parameters.sh ${environment} --confirm-delete-broken

Validation report: ${report_path}
EOF
  exit 1
fi

printf 'Runtime KMS validation passed for %s. Report: %s\n' "${environment}" "${report_path}"
