# aiops-control-plane

Composes the AIOps control-plane modules converted from `AIOPs_SAM/template.yaml`.

This module creates/wires:

- Lambda anomaly processor
- DynamoDB anomaly table
- SQS remediation queue and DLQ
- SNS notification topic
- EventBridge schedule, event bus, and anomaly event rule
- SSM runtime parameters
- Secrets Manager Jira credential secret shell
- CloudWatch dashboard and DLQ alarm
- Optional Managed Grafana workspace

Lambda code is not built here. Jenkins must provide either a local zip path for dev or an S3 artifact reference for promoted environments.
