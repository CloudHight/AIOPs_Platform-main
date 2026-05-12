# Architecture

The platform monitors an EC2-hosted Nginx workload, detects CPU and log anomalies with SageMaker endpoints, records operational state, alerts humans, creates Jira incidents, and schedules safe remediation through an SQS grace period.

## End-to-End Flow

```text
1. Jenkins trains and validates models.
2. Jenkins uploads approved model artifacts to S3.
3. Terraform deploys SageMaker endpoints using approved artifacts.
4. Terraform provisions the monitored EC2 workload.
5. EC2 publishes CPU metrics and Nginx logs to CloudWatch.
6. EventBridge invokes Lambda on a schedule.
7. Lambda discovers tagged EC2 instances.
8. Lambda fetches metrics/logs and invokes SageMaker endpoints.
9. Lambda records anomalies in DynamoDB.
10. Lambda sends SNS alerts and creates Jira tickets.
11. Lambda sends delayed SQS remediation messages.
12. Remediation handler re-checks the anomaly and safely acts if needed.
```

## Component Diagram

```text
                 +------------------+
                 |     Jenkins      |
                 +--------+---------+
                          |
        +-----------------+------------------+
        |                                    |
        v                                    v
  Model artifacts S3                 Lambda artifact S3
        |                                    |
        +-----------------+------------------+
                          |
                          v
                    Terraform apply
                          |
       +------------------+--------------------+
       |                  |                    |
       v                  v                    v
 EC2 workload       SageMaker endpoints    AIOps control plane
       |                  ^                    |
       v                  |                    v
 CloudWatch metrics/logs  +------------- Lambda detection
                                                |
               +--------------------------------+-----------------+
               |                  |             |                 |
               v                  v             v                 v
          DynamoDB state        SNS         Jira API       SQS grace queue
                                                                  |
                                                                  v
                                                         Lambda remediation
```

## Terraform Layer

Terraform modules live in `infra/modules/`:

- `ec2-workload`: EC2 instance, IAM instance profile, security group, Nginx/Docker/CloudWatch Agent bootstrap, workload log groups.
- `sagemaker-endpoint`: SageMaker model, endpoint configuration, endpoint, and endpoint alarms.
- `aiops-control-plane`: composition module for Lambda, DynamoDB, SQS, SNS, EventBridge, SSM, Secrets Manager, and CloudWatch observability.
- `lambda-function`: Lambda package deployment, execution role, policy, log group, and SQS event source mapping.
- `dynamodb`: anomaly state table with TTL, point-in-time recovery, and indexes.
- `sqs`: remediation processing queue and DLQ.
- `sns`: notification topic and optional email subscription.
- `eventbridge`: scheduled Lambda invocation and anomaly event routing.
- `ssm-parameters`: runtime thresholds and remediation feature flags.
- `secrets-manager`: Jira credential secret shell.
- `cloudwatch-observability`: dashboard, alarms, and log metric filters.

Environment roots live in `infra/envs/dev`, `infra/envs/stage`, and `infra/envs/prod`.

## Lambda Runtime

The Lambda handler is `aiops.handler.lambda_handler`.

Scheduled detection path:

1. Load environment variables and SSM runtime config.
2. Discover EC2 instances tagged `Project=AIOPs` and `AnomalyMonitoring=enabled`.
3. Read CPU metrics from CloudWatch.
4. Read recent Nginx error evidence from CloudWatch Logs.
5. Invoke CPU and log SageMaker endpoints.
6. Record or update an open anomaly in DynamoDB.
7. Publish lifecycle events to EventBridge.
8. Publish SNS alert.
9. Create Jira incident if no Jira issue is already stored.
10. Schedule SQS remediation recheck.

SQS remediation path:

1. Reload the anomaly record from DynamoDB.
2. Recheck the current signal.
3. Close recovered anomalies.
4. Skip remediation when dry-run, disabled, cooldown, attempt limit, tag, or environment policy blocks it.
5. For CPU anomalies, reboot the EC2 instance only when explicitly enabled.
6. For log anomalies, run approved SSM commands to restart Nginx and the app container.
7. Record status and emit EventBridge lifecycle event.

## Anomaly State Model

Lifecycle:

```text
DETECTED -> RECORDED -> ALERTED -> TICKETED -> GRACE_PERIOD -> RECHECKED -> REMEDIATED -> VERIFIED -> CLOSED
```

Failure and skip states:

```text
ALERT_FAILED
JIRA_FAILED
REMEDIATION_SKIPPED
REMEDIATION_FAILED
FALSE_POSITIVE
```

DynamoDB stores:

- deterministic `anomaly_id`
- deterministic `correlation_id`
- instance ID and anomaly type
- score, threshold, severity, and evidence
- Jira issue key
- remediation attempts
- timestamps for detection, alerting, ticketing, scheduling, recheck, and resolution
- TTL for old records

## Observability

CloudWatch dashboard sections:

- Lambda invocations, errors, duration, throttles
- SageMaker invocations, latency, 4XX, 5XX
- SQS queue depth, in-flight messages, oldest message age, DLQ depth
- DynamoDB capacity, latency, throttles
- EC2 CPU and status checks
- Nginx error event volume
- incident-flow Lambda logs

Critical alarms route to SNS.

## Security Boundaries

- Terraform owns resource lifecycle.
- Jenkins assumes environment-specific AWS roles.
- Secrets are not passed through Terraform variable files.
- EC2 access is through SSM, not SSH.
- Lambda remediation permissions are constrained by EC2 tags.
- Jira credentials are read from Secrets Manager.
- Operational flags are read from SSM Parameter Store.
