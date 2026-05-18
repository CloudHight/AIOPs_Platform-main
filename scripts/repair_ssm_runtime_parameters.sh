#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: scripts/repair_ssm_runtime_parameters.sh <dev|stage|prod> --confirm-delete-broken

Deletes only the known AIOps runtime SSM parameters that are broken because
their SecureString KMS key is missing, disabled, pending deletion, or cannot
decrypt the value. Terraform will recreate the parameters on the next apply.

This is intentionally manual and requires the confirmation flag.
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -ne 2 || "${2}" != "--confirm-delete-broken" ]]; then
  usage >&2
  exit 2
fi

environment="$1"
case "${environment}" in
  dev | stage | prod) ;;
  *)
    printf 'SSM repair failed: unsupported environment "%s".\n' "${environment}" >&2
    exit 2
    ;;
esac

for required in aws jq; do
  if ! command -v "${required}" >/dev/null 2>&1; then
    printf 'SSM repair failed: required command not found: %s\n' "${required}" >&2
    exit 2
  fi
done

parameter_prefix="/AnomalyDetection/${environment}"
parameter_names=(
  "${parameter_prefix}/AutoRemediationEnabled"
  "${parameter_prefix}/DryRun"
  "${parameter_prefix}/GracePeriodMinutes"
  "${parameter_prefix}/CpuThreshold"
  "${parameter_prefix}/LogThreshold"
  "${parameter_prefix}/MaxRemediationAttempts"
  "${parameter_prefix}/RemediationCooldownMinutes"
)

deleted=0
kept=0

for name in "${parameter_names[@]}"; do
  parameter_json="$(
    aws ssm describe-parameters \
      --parameter-filters "Key=Name,Option=BeginsWith,Values=${name}" \
      --output json |
      jq --arg name "${name}" '{Parameters: [.Parameters[] | select(.Name == $name)]}'
  )"
  parameter_count="$(printf '%s' "${parameter_json}" | jq '.Parameters | length')"

  if [[ "${parameter_count}" -eq 0 ]]; then
    printf 'Absent: %s\n' "${name}"
    continue
  fi

  parameter_type="$(printf '%s' "${parameter_json}" | jq -r '.Parameters[0].Type')"
  key_id="$(printf '%s' "${parameter_json}" | jq -r '.Parameters[0].KeyId // ""')"
  broken=false

  if [[ "${parameter_type}" == "SecureString" ]]; then
    if [[ -z "${key_id}" ]]; then
      broken=true
    elif ! key_json="$(aws kms describe-key --key-id "${key_id}" 2>/dev/null)"; then
      broken=true
    else
      key_state="$(printf '%s' "${key_json}" | jq -r '.KeyMetadata.KeyState')"
      if [[ "${key_state}" != "Enabled" ]]; then
        broken=true
      elif ! aws ssm get-parameter --name "${name}" --with-decryption --query 'Parameter.Name' --output text >/dev/null 2>&1; then
        broken=true
      fi
    fi
  fi

  if [[ "${broken}" == "true" ]]; then
    aws ssm delete-parameter --name "${name}" >/dev/null
    printf 'Deleted broken parameter: %s\n' "${name}"
    deleted=$((deleted + 1))
  else
    printf 'Kept readable parameter: %s\n' "${name}"
    kept=$((kept + 1))
  fi
done

printf 'SSM repair complete for %s. Deleted=%s Kept=%s\n' "${environment}" "${deleted}" "${kept}"
printf 'Next step: rerun Jenkins or run terraform plan/apply for infra/envs/%s.\n' "${environment}"
