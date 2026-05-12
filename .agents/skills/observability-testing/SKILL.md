---
description: Use when adding monitoring, dashboards, alarms, smoke tests, synthetic anomaly tests, or operational validation for the AIOps platform.
---

# Observability and Testing Skill

## Goal
Ensure the platform proves it works end-to-end and is observable in production.

## Use this skill when
- Building CloudWatch dashboards or alarms.
- Writing smoke tests.
- Creating synthetic CPU/log anomalies.
- Validating Lambda, SageMaker, DynamoDB, SQS, SNS, EventBridge, and Jira behavior.
- Writing runbooks for operations.

## Observability resources
Terraform should create:

- CloudWatch log groups with retention for Lambda and workload logs.
- CloudWatch dashboard for platform health.
- CloudWatch alarms for critical failures.
- Optional Managed Grafana workspace only if fully implemented and tested.

## Recommended CloudWatch alarms
Create alarms for:

- Lambda `Errors > 0` over evaluation period.
- Lambda `Throttles > 0`.
- Lambda duration approaching timeout.
- SQS DLQ visible messages > 0.
- SQS oldest message age too high.
- SageMaker endpoint 4XX/5XX invocation errors.
- SageMaker model latency above threshold.
- DynamoDB throttled requests.
- EC2 status check failure.
- CloudWatch Agent/log ingestion missing for monitored instance.

## Dashboard sections
Include dashboard widgets for:

1. Lambda health
   - invocations
   - errors
   - duration
   - throttles
2. SageMaker endpoints
   - invocations
   - latency
   - 4XX/5XX errors
3. Remediation queue
   - visible messages
   - age of oldest message
   - DLQ messages
4. DynamoDB
   - consumed capacity
   - throttles
   - successful writes
5. Workload
   - CPU utilization
   - status checks
   - Nginx error log volume
6. Incident flow
   - anomalies detected
   - remediations scheduled
   - remediations completed/failed

## Testing pyramid
Implement tests at these levels:

### Unit tests
- Python pure logic.
- Config parsing.
- Payload formatting.
- Response parsing.
- Dedupe/idempotency logic.

### Integration tests
- Boto3 clients using stubs where possible.
- Terraform module validation.
- Lambda package import check.

### Smoke tests after apply
- Read Terraform outputs.
- Check EC2 tag discovery.
- Confirm CloudWatch CPU metrics are recent.
- Confirm Nginx log group has recent entries.
- Invoke SageMaker endpoints with known samples.
- Invoke Lambda with a scheduled test event.
- Confirm SQS/SNS/EventBridge/DynamoDB resources exist.

### Synthetic anomaly tests
- CPU: run a controlled CPU stress command through SSM or workload script.
- Logs: generate known Nginx 5xx/timeout-style logs.
- Confirm anomaly record, alert, event, and remediation scheduling.

## Smoke test script contract
Create `scripts/smoke_test.sh <environment>`.

The script should:

- fail fast with clear error messages
- read Terraform outputs from `infra/envs/<environment>`
- avoid destructive tests unless `ALLOW_REMEDIATION_TEST=true`
- emit a final summary table
- return non-zero on failure

## Acceptance criteria
Observability/testing is complete when:

- Jenkins runs unit and smoke tests.
- Dashboards show platform health.
- Alarms cover critical failure modes.
- A synthetic anomaly can be detected end-to-end.
- The runbook explains how to troubleshoot each alarm.
