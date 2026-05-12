# cloudwatch-observability

CloudWatch observability resources converted from `AIOPs_SAM/template.yaml`.

Creates:

- CloudWatch dashboard for Lambda, SageMaker, SQS, DynamoDB, workload, and incident-flow health
- Lambda error, throttle, and duration alarms
- SQS DLQ and oldest-message-age alarms
- DynamoDB throttled-request alarm
- EC2 workload status-check alarm
- Nginx error log metric filter and alarm
- Optional AWS Managed Grafana workspace
