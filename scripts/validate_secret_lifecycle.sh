#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage: scripts/validate_secret_lifecycle.sh <tfplan.json>

Validates planned Secrets Manager secret creations before Terraform apply.
The script fails if a planned secret name already exists or is scheduled for
deletion, because Terraform cannot create a secret with either condition.
USAGE
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  usage
  exit 0
fi

plan_json="${1:-}"
if [ -z "${plan_json}" ]; then
  usage
  exit 2
fi

if [ ! -s "${plan_json}" ]; then
  echo "Terraform plan JSON was not found or is empty: ${plan_json}" >&2
  exit 2
fi

command -v aws >/dev/null
command -v jq >/dev/null

secret_names_file="$(mktemp)"
errors_file="$(mktemp)"
trap 'rm -f "${secret_names_file}" "${errors_file}"' EXIT

jq -r '
  (.resource_changes // [])
  | .[]
  | select(.mode == "managed")
  | select(.type == "aws_secretsmanager_secret")
  | select(.change.actions | index("create"))
  | .change.after.name // empty
' "${plan_json}" | sort -u >"${secret_names_file}"

if [ ! -s "${secret_names_file}" ]; then
  echo "No planned Secrets Manager secret creations found."
  exit 0
fi

failed=0
while IFS= read -r secret_name; do
  [ -n "${secret_name}" ] || continue

  describe_output=""
  if describe_output="$(aws secretsmanager describe-secret --secret-id "${secret_name}" --output json 2>"${errors_file}")"; then
    deleted_date="$(printf '%s' "${describe_output}" | jq -r '.DeletedDate // empty')"
    if [ -n "${deleted_date}" ]; then
      cat >&2 <<EOF
Secrets Manager lifecycle conflict: ${secret_name}
Status: scheduled for deletion at ${deleted_date}
Fix: run "aws secretsmanager restore-secret --secret-id ${secret_name}" and import/reuse it, or set jira_secret_name to a new stable environment-specific name.
EOF
    else
      cat >&2 <<EOF
Secrets Manager lifecycle conflict: ${secret_name}
Status: active secret already exists, but Terraform plan wants to create it.
Fix: import the existing secret into Terraform state, or set jira_secret_name to a new stable environment-specific name.
EOF
    fi
    failed=1
    continue
  fi

  if grep -q 'ResourceNotFoundException' "${errors_file}"; then
    echo "Secrets Manager name is available: ${secret_name}"
    continue
  fi

  echo "Failed to validate Secrets Manager secret ${secret_name}:" >&2
  cat "${errors_file}" >&2
  failed=1
done <"${secret_names_file}"

if [ "${failed}" -ne 0 ]; then
  exit 1
fi

echo "Secrets Manager lifecycle validation passed."
