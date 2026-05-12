# Terraform Backend

Bootstraps Terraform remote-state resources:

- KMS key and alias for state encryption
- S3 state bucket with versioning, encryption, and public access block
- DynamoDB lock table with point-in-time recovery

Apply this module once before enabling backend blocks in environment roots.

## Bootstrap

```bash
cd infra/backend
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform plan -out=tfplan
terraform apply tfplan
```

The values in `terraform.tfvars` must match the active backend block in the
environment root, for example `infra/envs/dev/versions.tf`.

## Validate

After bootstrap, validate the backend from the same AWS account and role that
Jenkins will use:

```bash
scripts/validate_terraform_backend.sh infra/envs/dev
```

The validator checks:

- S3 state bucket reachability
- S3 versioning
- S3 public access block
- S3 SSE-KMS encryption
- DynamoDB lock table reachability
- DynamoDB `LockID` hash key
- DynamoDB point-in-time recovery
- DynamoDB server-side encryption

Do not bypass Terraform locking with `-lock=false` for normal delivery. If this
validation fails in Jenkins, repair or bootstrap `infra/backend` in the target
account/region before rerunning the pipeline.
