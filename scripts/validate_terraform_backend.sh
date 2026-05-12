#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: scripts/validate_terraform_backend.sh <terraform-root>

Validates that the active S3 backend in <terraform-root>/versions.tf exists and
has the required production controls before Jenkins runs terraform init/plan.

Set AIOPS_BACKEND_PARSE_ONLY=true to validate backend parsing without AWS calls.
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

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF_ROOT="$1"

if [[ ! -d "${TF_ROOT}" ]]; then
  printf 'Terraform root does not exist: %s\n' "${TF_ROOT}" >&2
  exit 2
fi

VERSIONS_FILE="${TF_ROOT}/versions.tf"
if [[ ! -f "${VERSIONS_FILE}" ]]; then
  printf 'Terraform backend validation failed: %s is missing.\n' "${VERSIONS_FILE}" >&2
  exit 2
fi

backend_block="$(
  awk '
    /^[[:space:]]*#/ { next }
    /backend[[:space:]]+"s3"/ { in_backend = 1 }
    in_backend { print }
    in_backend && /^[[:space:]]*}/ { exit }
  ' "${VERSIONS_FILE}"
)"

if [[ -z "${backend_block}" ]]; then
  printf 'Terraform backend validation failed: no active backend "s3" block found in %s.\n' "${VERSIONS_FILE}" >&2
  printf 'Jenkins deployments require remote S3 state and DynamoDB locking. Bootstrap infra/backend first, then enable the backend block.\n' >&2
  exit 1
fi

extract_backend_value() {
  local key="$1"
  printf '%s\n' "${backend_block}" |
    awk -v key="${key}" '
      $1 == key && $2 == "=" {
        value = $3
        gsub(/^"/, "", value)
        gsub(/"$/, "", value)
        print value
        exit
      }
    '
}

bucket="$(extract_backend_value bucket)"
state_key="$(extract_backend_value key)"
region="$(extract_backend_value region)"
lock_table="$(extract_backend_value dynamodb_table)"
encrypt="$(extract_backend_value encrypt)"

missing=()
[[ -n "${bucket}" ]] || missing+=("bucket")
[[ -n "${state_key}" ]] || missing+=("key")
[[ -n "${region}" ]] || missing+=("region")
[[ -n "${lock_table}" ]] || missing+=("dynamodb_table")

if [[ ${#missing[@]} -gt 0 ]]; then
  printf 'Terraform backend validation failed: missing backend setting(s): %s\n' "${missing[*]}" >&2
  exit 1
fi

if [[ "${encrypt}" != "true" ]]; then
  printf 'Terraform backend validation failed: backend encrypt must be true in %s.\n' "${VERSIONS_FILE}" >&2
  exit 1
fi

mkdir -p "${ROOT_DIR}/reports"
report_path="${ROOT_DIR}/reports/terraform-backend-${TF_ROOT##*/}.txt"

{
  printf 'Terraform backend validation\n'
  printf 'Terraform root: %s\n' "${TF_ROOT}"
  printf 'State bucket: %s\n' "${bucket}"
  printf 'State key: %s\n' "${state_key}"
  printf 'Lock table: %s\n' "${lock_table}"
  printf 'Region: %s\n' "${region}"
} > "${report_path}"

if [[ "${AIOPS_BACKEND_PARSE_ONLY:-false}" == "true" ]]; then
  printf 'Backend parse validation passed for %s. AWS validation skipped by AIOPS_BACKEND_PARSE_ONLY.\n' "${TF_ROOT}"
  exit 0
fi

for required in aws jq; do
  if ! command -v "${required}" >/dev/null 2>&1; then
    printf 'Terraform backend validation failed: required command not found: %s\n' "${required}" >&2
    exit 2
  fi
done

account_id="$(aws sts get-caller-identity --query Account --output text)"
caller_arn="$(aws sts get-caller-identity --query Arn --output text)"

{
  printf 'AWS account: %s\n' "${account_id}"
  printf 'AWS caller: %s\n' "${caller_arn}"
} >> "${report_path}"

if ! aws s3api head-bucket --bucket "${bucket}" >/dev/null 2>&1; then
  cat >&2 <<EOF
Terraform backend validation failed: S3 state bucket "${bucket}" is not reachable by the Jenkins deploy role.

Bootstrap or repair infra/backend in account ${account_id}, region ${region}, then rerun this pipeline.
EOF
  exit 1
fi

bucket_versioning="$(
  aws s3api get-bucket-versioning --bucket "${bucket}" |
    jq -r '.Status // "Disabled"'
)"
if [[ "${bucket_versioning}" != "Enabled" ]]; then
  printf 'Terraform backend validation failed: S3 state bucket "%s" must have versioning enabled.\n' "${bucket}" >&2
  exit 1
fi

if ! aws s3api get-public-access-block --bucket "${bucket}" >/dev/null 2>&1; then
  printf 'Terraform backend validation failed: S3 state bucket "%s" must have public access block configured.\n' "${bucket}" >&2
  exit 1
fi

bucket_sse="$(
  aws s3api get-bucket-encryption --bucket "${bucket}" |
    jq -r '.ServerSideEncryptionConfiguration.Rules[0].ApplyServerSideEncryptionByDefault.SSEAlgorithm // ""'
)"
if [[ "${bucket_sse}" != "aws:kms" ]]; then
  printf 'Terraform backend validation failed: S3 state bucket "%s" must use SSE-KMS.\n' "${bucket}" >&2
  exit 1
fi

if ! table_json="$(aws dynamodb describe-table --table-name "${lock_table}" --region "${region}" 2>/dev/null)"; then
  cat >&2 <<EOF
Terraform backend validation failed: DynamoDB lock table "${lock_table}" was not found or is not readable in ${region}.

Expected backend:
  bucket         = "${bucket}"
  dynamodb_table = "${lock_table}"
  region         = "${region}"

Bootstrap infra/backend with matching values before running Jenkins:
  cd infra/backend
  terraform init
  terraform apply
EOF
  exit 1
fi

table_status="$(printf '%s' "${table_json}" | jq -r '.Table.TableStatus')"
if [[ "${table_status}" != "ACTIVE" ]]; then
  printf 'Terraform backend validation failed: DynamoDB lock table "%s" status is %s, expected ACTIVE.\n' "${lock_table}" "${table_status}" >&2
  exit 1
fi

lock_key_schema="$(
  printf '%s' "${table_json}" |
    jq -r '.Table.KeySchema[] | select(.AttributeName == "LockID" and .KeyType == "HASH") | .AttributeName'
)"
if [[ "${lock_key_schema}" != "LockID" ]]; then
  printf 'Terraform backend validation failed: DynamoDB lock table "%s" must use LockID as HASH key.\n' "${lock_table}" >&2
  exit 1
fi

pitr_status="$(
  aws dynamodb describe-continuous-backups --table-name "${lock_table}" --region "${region}" |
    jq -r '.ContinuousBackupsDescription.PointInTimeRecoveryDescription.PointInTimeRecoveryStatus // "DISABLED"'
)"
if [[ "${pitr_status}" != "ENABLED" ]]; then
  printf 'Terraform backend validation failed: DynamoDB lock table "%s" must have point-in-time recovery enabled.\n' "${lock_table}" >&2
  exit 1
fi

ddb_sse_status="$(printf '%s' "${table_json}" | jq -r '.Table.SSEDescription.Status // "UNKNOWN"')"
if [[ "${ddb_sse_status}" != "ENABLED" ]]; then
  printf 'Terraform backend validation failed: DynamoDB lock table "%s" must use server-side encryption.\n' "${lock_table}" >&2
  exit 1
fi

{
  printf 'S3 versioning: %s\n' "${bucket_versioning}"
  printf 'S3 encryption: %s\n' "${bucket_sse}"
  printf 'DynamoDB table status: %s\n' "${table_status}"
  printf 'DynamoDB PITR: %s\n' "${pitr_status}"
  printf 'DynamoDB SSE: %s\n' "${ddb_sse_status}"
  printf 'Validation result: passed\n'
} >> "${report_path}"

printf 'Terraform backend validation passed for %s. Report: %s\n' "${TF_ROOT}" "${report_path}"
