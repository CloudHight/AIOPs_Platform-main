# Operations Runbook

This runbook covers alert response, incident handling, remediation, rollback, and cleanup.

## Dashboard

Open the dashboard:

```bash
terraform -chdir=infra/envs/dev output aiops_cloudwatch_dashboard_name
```

Dashboard sections:

- Lambda health
- SageMaker endpoints
- SQS remediation queues
- DynamoDB anomaly table
- EC2 workload health
- Nginx error volume
- incident-flow logs

## Common Commands

Get environment outputs:

```bash
terraform -chdir=infra/envs/dev output
```

Read Lambda logs:

```bash
aws logs tail "/aws/lambda/$(terraform -chdir=infra/envs/dev output -raw aiops_lambda_function_name)" --since 30m
```

List open anomalies:

```bash
TABLE="$(terraform -chdir=infra/envs/dev output -raw aiops_dynamodb_table_name)"
aws dynamodb scan \
  --table-name "$TABLE" \
  --filter-expression "#s IN (:recorded,:alerted,:ticketed,:grace,:rechecked)" \
  --expression-attribute-names '{"#s":"status"}' \
  --expression-attribute-values '{
    ":recorded":{"S":"RECORDED"},
    ":alerted":{"S":"ALERTED"},
    ":ticketed":{"S":"TICKETED"},
    ":grace":{"S":"GRACE_PERIOD"},
    ":rechecked":{"S":"RECHECKED"}
  }'
```

## Lambda Errors Alarm

Symptom: `aiops-lambda-errors-<env>` is in `ALARM`.

Likely causes:

- missing environment variable
- IAM denial
- SageMaker timeout
- Jira secret missing or malformed
- malformed inference response

First checks:

```bash
FUNCTION="$(terraform -chdir=infra/envs/dev output -raw aiops_lambda_function_name)"
aws logs tail "/aws/lambda/$FUNCTION" --since 30m
aws lambda get-function-configuration --function-name "$FUNCTION"
```

Remediation:

1. Fix missing config or secret.
2. Re-run Jenkins package and Terraform apply if code/config changed.
3. Run `scripts/smoke_test.sh dev`.

Escalate if errors continue after rollback or affect prod.

## Lambda Throttles Alarm

Symptom: Lambda throttles are greater than zero.

Likely causes:

- account concurrency pressure
- SQS batch volume
- long-running downstream calls

First checks:

```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Throttles \
  --dimensions Name=FunctionName,Value="$(terraform -chdir=infra/envs/dev output -raw aiops_lambda_function_name)" \
  --start-time "$(date -u -v-30M +%Y-%m-%dT%H:%M:%SZ)" \
  --end-time "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --period 300 \
  --statistics Sum
```

Remediation:

- increase concurrency limits if appropriate
- reduce SQS batch/window pressure
- investigate slow SageMaker/Jira calls

## Lambda Duration Alarm

Symptom: average duration approaches timeout.

Likely causes:

- SageMaker latency
- CloudWatch Logs query latency
- Jira API slowness
- too many instances in one invocation

First checks:

```bash
aws logs tail "/aws/lambda/$(terraform -chdir=infra/envs/dev output -raw aiops_lambda_function_name)" --since 30m
```

Remediation:

- reduce per-invocation workload
- tune timeouts and retries
- investigate SageMaker endpoint metrics

## SQS DLQ Alarm

Symptom: remediation DLQ has visible messages.

Likely causes:

- remediation handler exception
- malformed queued payload
- IAM denial for EC2/SSM
- DynamoDB record missing

First checks:

```bash
aws sqs receive-message \
  --queue-url "$(terraform -chdir=infra/envs/dev output -raw aiops_sqs_processing_queue_url)" \
  --attribute-names All \
  --message-attribute-names All \
  --max-number-of-messages 1
```

Remediation:

1. Inspect Lambda logs around the failure time.
2. Fix code/IAM/config.
3. Redrive or replay only after confirming idempotency.

## SQS Oldest Message Age Alarm

Symptom: remediation queue backlog is aging.

Likely causes:

- Lambda event source mapping disabled
- Lambda throttling
- repeated requeue during long grace period

First checks:

```bash
aws lambda list-event-source-mappings \
  --function-name "$(terraform -chdir=infra/envs/dev output -raw aiops_lambda_function_name)"
```

Remediation:

- enable event source mapping
- resolve Lambda errors/throttles
- inspect queue depth and DLQ

## DynamoDB Throttles Alarm

Symptom: anomaly table has throttled requests.

Likely causes:

- hot partition by status/index
- unexpected detection volume
- account-level DynamoDB constraints

First checks:

```bash
aws dynamodb describe-table \
  --table-name "$(terraform -chdir=infra/envs/dev output -raw aiops_dynamodb_table_name)"
```

Remediation:

- keep PAY_PER_REQUEST enabled
- review access patterns
- add targeted indexes only when justified

## EC2 Status Check Alarm

Symptom: workload status check failed.

Likely causes:

- instance host issue
- kernel/system failure
- exhausted resources

First checks:

```bash
INSTANCE="$(terraform -chdir=infra/envs/dev output -raw workload_instance_id)"
aws ec2 describe-instance-status --instance-ids "$INSTANCE" --include-all-instances
aws ssm start-session --target "$INSTANCE"
```

Remediation:

- inspect system logs through SSM
- restart application services
- reboot only through approved remediation path or change process

## Nginx Error Volume Alarm

Symptom: Nginx error event metric exceeds threshold.

Likely causes:

- application container unhealthy
- upstream timeout
- bad deploy
- traffic spike

First checks:

```bash
aws logs tail "$(terraform -chdir=infra/envs/dev output -raw workload_nginx_error_log_group_name)" --since 30m
```

Remediation:

- validate application container
- check Nginx config
- run synthetic log validation only in dev/stage

## Smoke Validation

```bash
scripts/smoke_test.sh dev
```

Synthetic anomaly validation:

```bash
ALLOW_SYNTHETIC_ANOMALY_TEST=true scripts/smoke_test.sh dev
```

## Rollback

Lambda rollback:

1. Select previous Lambda artifact key/version.
2. Set Terraform Lambda artifact variables.
3. Run Jenkins plan/apply.
4. Smoke-test.

Model rollback:

1. Select previous immutable model artifact URI.
2. Update model tfvars.
3. Run Jenkins plan/apply.
4. Invoke endpoint smoke tests.

Infrastructure rollback:

1. Revert the code change.
2. Re-run Jenkins to produce a fresh plan.
3. Apply the saved plan.

## Cleanup

Local cleanup:

```bash
scripts/cleanup_ephemeral.sh
```

Environment destroy:

```bash
terraform -chdir=infra/envs/dev plan -destroy -out=destroy.tfplan
terraform -chdir=infra/envs/dev apply destroy.tfplan
```
