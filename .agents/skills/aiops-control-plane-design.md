# Supporting note — AIOps control-plane resource map

This file is supporting context for skills. It is not a skill entrypoint.

## Core resources to migrate from SAM to Terraform

- Lambda anomaly processor/remediation handler
- IAM role and policies for Lambda
- DynamoDB anomaly table with TTL
- SNS topic and subscriptions
- SQS remediation queue
- SQS dead-letter queue
- EventBridge schedule/rule
- EventBridge custom bus for audit events
- SSM parameters for thresholds and runtime config
- Secrets Manager secret for Jira credentials
- CloudWatch log groups
- CloudWatch dashboard/alarms

## Core behavior to preserve

- Discover EC2 instances by tag.
- Read CPU metrics from CloudWatch.
- Read Nginx logs from CloudWatch Logs.
- Invoke CPU and log SageMaker endpoints.
- Store anomalies.
- Alert via SNS.
- Create Jira tickets.
- Delay remediation through SQS.
- Re-check before remediation.
- Execute safe EC2/SSM remediation.
