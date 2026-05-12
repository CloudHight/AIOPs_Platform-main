# Project Defense

Use this as a technical Q&A guide when explaining the project.

## Why Terraform Instead Of SAM For Final Delivery?

SAM is good for Lambda-centric applications, but this platform spans EC2, SageMaker, DynamoDB, SQS, SNS, EventBridge, SSM, Secrets Manager, dashboards, alarms, and backend state. Terraform gives one infrastructure graph, one plan, one approval artifact, and reusable modules across dev, stage, and prod.

## Why Jenkins For CI/CD?

Jenkins is the orchestrator for actions that should not be done by Terraform:

- model training
- model validation
- artifact packaging
- security scanning
- Terraform plan archival
- approval gates
- smoke tests

Terraform should only converge infrastructure.

## Why Not Train Models Inside Terraform?

Training is procedural, long-running, data-dependent, and produces artifacts. Terraform is declarative infrastructure state. Putting training inside Terraform would make plans non-repeatable and make state depend on external training behavior. Jenkins creates immutable artifacts first; Terraform deploys approved URIs.

## How Does CPU Anomaly Detection Work?

The workload publishes EC2 `CPUUtilization` metrics to CloudWatch. Lambda reads recent CPU statistics, builds an inference payload, invokes the CPU SageMaker endpoint, and compares the returned score against the SSM-configured CPU threshold. If the score crosses the threshold, Lambda records an anomaly and starts the incident workflow.

## How Does Log Anomaly Detection Work?

The EC2 workload ships Nginx access and error logs to CloudWatch Logs. Lambda reads recent error evidence, builds a log inference payload, invokes the log SageMaker endpoint, and compares the returned score against the SSM-configured log threshold.

## How Does Lambda Discover Instances?

Lambda calls EC2 `DescribeInstances` and filters for:

```text
Project=AIOPs
AnomalyMonitoring=enabled
instance-state-name=running
```

The same tags are used as remediation guardrails.

## How Do CloudWatch Metrics And Logs Become Inference Payloads?

CPU payloads include recent CPU averages. Log payloads include error counts and sampled log lines. The inference helper accepts common SageMaker response shapes such as `score`, `anomaly_score`, `scores`, and `predictions`.

## How Does The SQS Grace Period Prevent Premature Remediation?

Detection schedules an SQS message for a future recheck. SQS supports a maximum delay of 15 minutes, so the remediation scheduler can requeue the message until `scheduled_for_epoch` is due. The remediation handler then reloads DynamoDB state and rechecks the current signal before acting.

## How Are Duplicate Jira Tickets Avoided?

The anomaly ID is deterministic:

```text
<environment>#<instance-id>#<anomaly-type>
```

DynamoDB stores the Jira issue key on the open anomaly record. Repeated detections update the existing record rather than creating a new ticket.

## How Is IAM Least Privilege Implemented?

IAM policies are scoped by ARN where possible. Remediation actions require resource tags. Secrets Manager access is limited to the Jira secret. SageMaker invoke access is limited to configured endpoints. SQS, SNS, DynamoDB, and EventBridge access is limited to platform resources.

## How Is The System Tested End-To-End?

Testing layers:

- unit tests for config parsing, score extraction, and model helpers
- shell syntax checks for delivery scripts
- Terraform fmt and validate
- Jenkins quality and security stages
- post-apply smoke tests
- optional synthetic CPU/log anomaly tests through SSM

## How Do You Roll Back A Bad Model?

Use the previous immutable S3 artifact URI and rerun Jenkins/Terraform. SageMaker model resources update from the approved URI. Never overwrite existing model prefixes.

## How Do You Roll Back A Bad Lambda Deployment?

Deploy the previous Lambda S3 artifact key/version and source hash through Jenkins. Terraform applies the previous package reference.

## How Are Credentials And State Secured?

Jira credentials live in Secrets Manager. Runtime flags live in SSM Parameter Store. Terraform state is stored in an encrypted S3 backend with DynamoDB locking. Jenkins stores role ARNs and artifact bucket names as credentials, not in source.

## What Is Still Environment-Specific?

Production environments should provide:

- restricted HTTP CIDRs or private load balancing
- KMS keys for all supported resources
- confirmed SNS subscriptions
- Jira secret values
- remote Terraform backend configuration
- stricter scanner failure policy in Jenkins
