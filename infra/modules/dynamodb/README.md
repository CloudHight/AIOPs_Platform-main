# dynamodb

Anomaly records table converted from `AIOPs_SAM/template.yaml`.

Creates a pay-per-request DynamoDB table with:

- `anomaly_id` partition key
- instance/timestamp, model/timestamp, and status/timestamp GSIs
- TTL on `ttl`
- point-in-time recovery
- server-side encryption with optional KMS key
