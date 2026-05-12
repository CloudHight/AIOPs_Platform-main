# Terraform Backend

Bootstraps Terraform remote-state resources:

- KMS key and alias for state encryption
- S3 state bucket with versioning, encryption, and public access block
- DynamoDB lock table with point-in-time recovery

Apply this module once before enabling backend blocks in environment roots.
