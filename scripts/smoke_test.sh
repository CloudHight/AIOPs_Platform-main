#!/usr/bin/env bash
set -euo pipefail

ENVIRONMENT="${1:-dev}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF_ROOT="${ROOT_DIR}/infra/envs/${ENVIRONMENT}"
REPORT_DIR="${ROOT_DIR}/reports/smoke"
REPORT_FILE="${REPORT_DIR}/${ENVIRONMENT}.json"
SUMMARY_FILE="${REPORT_DIR}/${ENVIRONMENT}.summary.txt"

mkdir -p "${REPORT_DIR}"
test -d "${TF_ROOT}"

OUTPUTS="$(cd "${TF_ROOT}" && terraform output -json)"
CHECK_RESULTS=()
FAILURES=0

value() {
  printf '%s' "${OUTPUTS}" | jq -r ".${1}.value // empty"
}

json_value() {
  printf '%s' "${OUTPUTS}" | jq -c ".${1}.value // []"
}

record_check() {
  local name="$1"
  local status="$2"
  local detail="${3:-}"
  CHECK_RESULTS+=("${name}|${status}|${detail}")
  printf '%-36s %s %s\n' "${name}" "${status}" "${detail}" | tee -a "${SUMMARY_FILE}"
  if [[ "${status}" == "FAIL" ]]; then
    FAILURES=$((FAILURES + 1))
  fi
}

run_check() {
  local name="$1"
  shift
  local output
  if output="$("$@" 2>&1)"; then
    record_check "${name}" "PASS" ""
  else
    record_check "${name}" "FAIL" "${output//$'\n'/ }"
  fi
}

require_output() {
  local name="$1"
  local value="$2"
  if [[ -n "${value}" && "${value}" != "null" ]]; then
    record_check "${name}" "PASS" "${value}"
  else
    record_check "${name}" "FAIL" "missing Terraform output"
  fi
}

write_report() {
  local checks_json="[]"
  for item in "${CHECK_RESULTS[@]}"; do
    IFS='|' read -r name status detail <<< "${item}"
    checks_json="$(jq -c \
      --arg name "${name}" \
      --arg status "${status}" \
      --arg detail "${detail}" \
      '. + [{name: $name, status: $status, detail: $detail}]' <<< "${checks_json}")"
  done
  jq -n \
    --arg environment "${ENVIRONMENT}" \
    --arg status "$([[ "${FAILURES}" -eq 0 ]] && printf passed || printf failed)" \
    --argjson checks "${checks_json}" \
    '{environment: $environment, status: $status, checks: $checks}' > "${REPORT_FILE}"
}

rm -f "${SUMMARY_FILE}"

INSTANCE_ID="$(value workload_instance_id)"
ACCESS_LOG_GROUP="$(value workload_nginx_access_log_group_name)"
ERROR_LOG_GROUP="$(value workload_nginx_error_log_group_name)"
LAMBDA_FUNCTION="$(value aiops_lambda_function_name)"
EVENT_BUS="$(value aiops_event_bus_name)"
DDB_TABLE="$(value aiops_dynamodb_table_name)"
SQS_QUEUE_URL="$(value aiops_sqs_processing_queue_url)"
DASHBOARD_NAME="$(value aiops_cloudwatch_dashboard_name)"
ALARM_NAMES="$(json_value aiops_cloudwatch_alarm_names)"
CPU_ENDPOINT="$(value cpu_sagemaker_endpoint_name)"
LOG_ENDPOINT="$(value log_sagemaker_endpoint_name)"

require_output "terraform_output_instance" "${INSTANCE_ID}"
run_check "ec2_tag_discovery" aws ec2 describe-instances \
  --instance-ids "${INSTANCE_ID}" \
  --filters "Name=tag:AnomalyMonitoring,Values=enabled" "Name=tag:Project,Values=AIOPs"

run_check "cloudwatch_cpu_metric_read" aws cloudwatch get-metric-statistics \
  --namespace AWS/EC2 \
  --metric-name CPUUtilization \
  --dimensions "Name=InstanceId,Value=${INSTANCE_ID}" \
  --start-time "$(python3 -u -c 'from datetime import datetime, timedelta, timezone; print((datetime.now(timezone.utc)-timedelta(minutes=30)).isoformat())')" \
  --end-time "$(python3 -u -c 'from datetime import datetime, timezone; print(datetime.now(timezone.utc).isoformat())')" \
  --period 300 \
  --statistics Average

for group in "${ACCESS_LOG_GROUP}" "${ERROR_LOG_GROUP}"; do
  if [[ -n "${group}" && "${group}" != "null" ]]; then
    run_check "logs_streams_${group//\//_}" aws logs describe-log-streams --log-group-name "${group}" --max-items 5
  fi
done

if [[ -n "${CPU_ENDPOINT}" && "${CPU_ENDPOINT}" != "null" ]]; then
  run_check "sagemaker_cpu_endpoint" aws sagemaker-runtime invoke-endpoint \
    --endpoint-name "${CPU_ENDPOINT}" \
    --content-type application/json \
    --cli-binary-format raw-in-base64-out \
    --body '{"instances":[{"cpu_average":75.0}]}' \
    "${REPORT_DIR}/cpu-endpoint-response.json"
else
  record_check "sagemaker_cpu_endpoint" "SKIP" "endpoint not managed by this environment"
fi

if [[ -n "${LOG_ENDPOINT}" && "${LOG_ENDPOINT}" != "null" ]]; then
  run_check "sagemaker_log_endpoint" aws sagemaker-runtime invoke-endpoint \
    --endpoint-name "${LOG_ENDPOINT}" \
    --content-type application/json \
    --cli-binary-format raw-in-base64-out \
    --body '{"instances":[{"error_count":3,"samples":["GET / HTTP/1.1 500"]}]}' \
    "${REPORT_DIR}/log-endpoint-response.json"
else
  record_check "sagemaker_log_endpoint" "SKIP" "endpoint not managed by this environment"
fi

if [[ -n "${LAMBDA_FUNCTION}" && "${LAMBDA_FUNCTION}" != "null" ]]; then
  run_check "lambda_test_invoke" aws lambda invoke \
    --function-name "${LAMBDA_FUNCTION}" \
    --cli-binary-format raw-in-base64-out \
    --payload "{\"instance_ids\":[\"${INSTANCE_ID}\"]}" \
    "${REPORT_DIR}/lambda-invoke-response.json"
else
  record_check "lambda_test_invoke" "SKIP" "control plane not enabled"
fi

if [[ -n "${DDB_TABLE}" && "${DDB_TABLE}" != "null" ]]; then
  run_check "dynamodb_table" aws dynamodb describe-table --table-name "${DDB_TABLE}"
else
  record_check "dynamodb_table" "SKIP" "control plane not enabled"
fi

if [[ -n "${SQS_QUEUE_URL}" && "${SQS_QUEUE_URL}" != "null" ]]; then
  run_check "sqs_processing_queue" aws sqs get-queue-attributes --queue-url "${SQS_QUEUE_URL}" --attribute-names QueueArn ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible
else
  record_check "sqs_processing_queue" "SKIP" "control plane not enabled"
fi

if [[ -n "${EVENT_BUS}" && "${EVENT_BUS}" != "null" ]]; then
  run_check "eventbridge_bus" aws events describe-event-bus --name "${EVENT_BUS}"
else
  record_check "eventbridge_bus" "SKIP" "control plane not enabled"
fi

if [[ -n "${DASHBOARD_NAME}" && "${DASHBOARD_NAME}" != "null" ]]; then
  run_check "cloudwatch_dashboard" aws cloudwatch get-dashboard --dashboard-name "${DASHBOARD_NAME}"
else
  record_check "cloudwatch_dashboard" "SKIP" "control plane not enabled"
fi

if [[ "${ALARM_NAMES}" != "[]" ]]; then
  mapfile -t ALARMS < <(jq -r '.[]' <<< "${ALARM_NAMES}")
  run_check "cloudwatch_alarms" aws cloudwatch describe-alarms --alarm-names "${ALARMS[@]}"
else
  record_check "cloudwatch_alarms" "SKIP" "control plane not enabled"
fi

if [[ "${ALLOW_SYNTHETIC_ANOMALY_TEST:-false}" == "true" ]]; then
  run_check "synthetic_cpu_anomaly_ssm" aws ssm send-command \
    --instance-ids "${INSTANCE_ID}" \
    --document-name AWS-RunShellScript \
    --comment "AIOps synthetic CPU anomaly test" \
    --parameters 'commands=["timeout 120 bash -c \"while true; do :; done\""]'
  run_check "synthetic_log_anomaly_ssm" aws ssm send-command \
    --instance-ids "${INSTANCE_ID}" \
    --document-name AWS-RunShellScript \
    --comment "AIOps synthetic Nginx log anomaly test" \
    --parameters 'commands=["for i in $(seq 1 10); do echo \"synthetic upstream timeout 500 aiops smoke\" | sudo tee -a /var/log/nginx/error.log >/dev/null; done"]'
else
  record_check "synthetic_anomaly_tests" "SKIP" "set ALLOW_SYNTHETIC_ANOMALY_TEST=true to run controlled SSM tests"
fi

write_report
printf 'Smoke summary: %s\n' "${SUMMARY_FILE}"
printf 'Smoke report: %s\n' "${REPORT_FILE}"

if [[ "${FAILURES}" -gt 0 ]]; then
  exit 1
fi
