# lambda-function

Packaged Lambda deployment converted from `AIOPs_SAM/template.yaml`.

Creates:

- Lambda execution role and scoped inline policy
- Lambda log group
- Lambda function
- SQS event source mapping

The function handler is `aiops.handler.lambda_handler`. It handles both scheduled anomaly detection and SQS grace-period remediation messages.

The module expects Jenkins to provide a Lambda zip through either local package path or S3 artifact inputs.
