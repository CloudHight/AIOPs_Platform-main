# SAM Migration Freeze

`AIOPs_SAM/` is now a read-only migration reference. It must not be used for deployment. The active delivery path is:

```text
Jenkinsfile -> scripts/package_lambda.sh -> lambda/src/aiops -> infra/modules -> infra/envs/<env>
```

## Deletion Gate

Remove `AIOPs_SAM/` only after a Jenkins run for the target release completes all of these stages successfully:

- Lambda package
- Terraform quality
- Terraform plan
- Terraform apply
- Smoke tests

The smoke test evidence must include:

- deployed Lambda invocation
- DynamoDB anomaly record write/read
- SQS remediation queue path
- SNS/EventBridge notification path
- SageMaker CPU and log endpoint invocation
- Jira dry-run or test-project incident path

The latest checked `jenkins-pipeline-logs` showed `Smoke Tests` skipped because an earlier stage failed, so `AIOPs_SAM/` remains in the repository as reference material.

## Behavior Coverage

| Legacy SAM responsibility | Current implementation | Status |
|---|---|---|
| Lambda entrypoint in `AIOPs_SAM/app.py` | `lambda/src/aiops/handler.py` | Covered. The handler routes scheduled detection events and SQS remediation events. |
| Environment variables and runtime configuration | `lambda/src/aiops/config.py`, `infra/modules/lambda-function`, `infra/modules/ssm-parameters` | Covered. Runtime flags and thresholds are deployed as SSM parameters and loaded by Lambda. |
| EC2 discovery by tag | `lambda/src/aiops/discovery.py` | Covered. Discovery remains tag based. |
| CPU metric collection | `lambda/src/aiops/metrics_reader.py` | Covered. CloudWatch metric reads are separated from orchestration logic. |
| Nginx/log collection | `lambda/src/aiops/logs_reader.py` | Covered. CloudWatch Logs reads are separated from orchestration logic. |
| SageMaker CPU and log inference | `lambda/src/aiops/inference.py`, `infra/modules/sagemaker-endpoint` | Covered. Terraform deploys endpoints from approved model artifacts; Lambda invokes configured endpoint names. |
| DynamoDB anomaly records, TTL, and indexes | `lambda/src/aiops/anomaly_store.py`, `infra/modules/dynamodb` | Covered. Terraform adds PITR, TTL, GSIs, and optional customer-managed KMS encryption. |
| SNS alerting | `lambda/src/aiops/alerting.py`, `infra/modules/sns` | Covered. Email confirmation remains an operator step. |
| Jira incident creation | `lambda/src/aiops/jira_client.py`, `infra/modules/secrets-manager` | Covered with safer secret handling. Terraform creates a secret shell; real Jira values are populated out of band. |
| SQS grace-period remediation | `lambda/src/aiops/remediation.py`, `infra/modules/sqs`, Lambda SQS event source mapping | Covered. The remediation queue and DLQ are Terraform-managed. |
| EventBridge schedule and custom event bus | `lambda/src/aiops/events.py`, `infra/modules/eventbridge` | Covered. Scheduled invocation and anomaly event fanout are Terraform-managed. |
| Lambda IAM, package, log group, DLQ, tracing | `infra/modules/lambda-function`, `scripts/package_lambda.sh`, Jenkinsfile | Covered. Jenkins packages the Lambda zip; Terraform deploys the function and event source mapping. |
| CloudWatch dashboard and alarms | `infra/modules/cloudwatch-observability` | Covered and expanded with Lambda, SQS, DynamoDB, SageMaker, and workload alarms. |
| Optional Managed Grafana | `infra/modules/cloudwatch-observability` | Partially covered. The workspace is optional; the old SAM custom bootstrap Lambda is not carried forward because the source is not present. |

## Intentional Differences

- SAM is no longer a deployment tool. Terraform owns AWS resources and Jenkins owns packaging and promotion.
- Jira secrets are no longer embedded in a template. Terraform creates the secret container, and operators or Jenkins credentials populate the real values.
- Customer-managed KMS support is added across Terraform modules where practical.
- IAM policies are scoped to explicit resources, tagged remediation targets, and configured endpoint ARNs instead of the broader SAM-era policy shape.
- Model training and validation happen before Terraform consumes immutable model artifact URIs.

## Removal Checklist

Before deleting `AIOPs_SAM/`, record the successful Jenkins build number and artifact version in the release notes, then remove:

- `AIOPs_SAM/`
- obsolete README references to SAM deployment
- any stale SAM commands from runbooks or test notes

Do not remove the folder while smoke tests are failing or skipped.
