# eventbridge

EventBridge resources converted from `AIOPs_SAM/template.yaml`.

Creates:

- Scheduled rule that invokes the anomaly Lambda
- Custom anomaly event bus
- Event rule that routes anomaly events to SNS
- Lambda invoke permission for the schedule
- SNS topic policy allowing EventBridge publish
