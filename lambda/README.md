# Lambda

Python package for the AIOps control plane.

Runtime flow:

1. EventBridge invokes `aiops.handler.lambda_handler` on the monitoring schedule.
2. The handler discovers tagged EC2 instances, reads CPU/log evidence, invokes SageMaker, and records open anomalies in DynamoDB.
3. New open anomalies publish SNS alerts, create Jira incidents, emit EventBridge lifecycle events, and schedule an SQS grace-period message.
4. SQS invokes the same handler for recheck/remediation. The handler reloads the anomaly, rechecks current signals, skips recovered signals, and only remediates when feature flags and safety gates allow it.

Automated remediation is safe by default: `AutoRemediationEnabled=false` and `DryRun=true` unless changed in SSM Parameter Store.
