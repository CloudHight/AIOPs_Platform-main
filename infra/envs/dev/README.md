# Dev Environment

Terraform root module for the AIOps development environment.

This root is intended for fast validation of the monitored EC2 workload, optional SageMaker endpoints, and optional AIOps control plane. Jenkins is the preferred apply path because it packages Lambda/model artifacts and archives the Terraform plan, but local plan/apply is supported for development.

## What This Root Deploys

Always deployed:

- environment KMS key and alias for service encryption
- EC2 monitored workload
- workload IAM role and instance profile
- HTTP security group
- Nginx access/error CloudWatch log groups
- workload bootstrap for Nginx, Docker app, CloudWatch Agent, SSM, and stress tooling

Optional when `enable_sagemaker_endpoints = true`:

- CPU RCF SageMaker endpoint
- Nginx/log SageMaker endpoint
- SageMaker model resources, endpoint configs, and endpoint alarms

Optional when `enable_aiops_control_plane = true`:

- Lambda anomaly processor
- DynamoDB anomaly table
- SQS remediation queue and DLQ
- SNS notification topic
- EventBridge schedule and custom event bus
- SSM runtime parameters
- Secrets Manager Jira credential shell
- CloudWatch dashboard and alarms

## Defaults

Dev defaults now start from the same hardened baseline as stage/prod:

```hcl
allowed_http_cidrs           = []
workload_instance_type       = "t3.medium"
workload_associate_public_ip = false
workload_log_retention_days  = 365
enable_aiops_control_plane   = false
enable_sagemaker_endpoints   = false
auto_remediation_enabled     = false
dry_run                      = true
```

The workload uses SSM Session Manager for administration, IMDSv2, encrypted EBS, detailed monitoring, KMS-encrypted logs, and HTTPS-only outbound security group egress. If you intentionally need a public demo endpoint in dev, set `allowed_http_cidrs` and `workload_associate_public_ip` explicitly in `terraform.tfvars` and document that exception for the run.

## Backend

Run `infra/backend` first, then configure the commented S3 backend block in `versions.tf`.

```bash
cd ../../backend
terraform init
terraform apply
```

After filling the backend block:

```bash
terraform init -migrate-state
```

## Local Plan

```bash
cd infra/envs/dev
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform fmt -check -recursive ../..
terraform validate
terraform plan -out=tfplan
```

Apply only after reviewing the plan:

```bash
terraform apply tfplan
```

## Enable The Control Plane Locally

Package Lambda first:

```bash
scripts/package_lambda.sh
```

Then set these values in `terraform.tfvars`:

```hcl
enable_aiops_control_plane = true
lambda_local_package_path  = "../../../dist/lambda/aiops-lambda.zip"
lambda_source_code_hash    = "<contents of dist/lambda/aiops-lambda.zip.base64sha256>"
```

For Jenkins/S3 artifact deployment, use:

```hcl
lambda_artifact_bucket   = "<lambda-artifact-bucket>"
lambda_artifact_key      = "lambda/dev/<build-number>/aiops-lambda.zip"
lambda_source_code_hash  = "<base64 sha256>"
```

## Enable SageMaker Endpoints

Jenkins normally writes model artifact variables through:

```bash
scripts/write_model_tfvars.sh infra/envs/dev/model-artifacts.auto.tfvars.json
```

Required values:

```hcl
enable_sagemaker_endpoints = true
model_version              = "<build-or-git-version>"
cpu_model_artifact_s3_uri  = "s3://..."
log_model_artifact_s3_uri  = "s3://..."
cpu_model_image_uri        = "<image-uri>"
log_model_image_uri        = "<image-uri>"
```

When both the control plane and SageMaker endpoints are enabled, Lambda receives the Terraform-managed endpoint names automatically.

## Runtime Safety

Remediation is safe by default:

```hcl
auto_remediation_enabled   = false
dry_run                    = true
max_remediation_attempts   = 1
remediation_cooldown_minutes = 60
```

The control plane also creates SSM parameters under:

```text
/AnomalyDetection/dev/
```

Change runtime remediation flags in SSM only after smoke tests and operational approval.

## Important Outputs

```bash
terraform output workload_instance_id
terraform output workload_nginx_access_log_group_name
terraform output workload_nginx_error_log_group_name
terraform output aiops_lambda_function_name
terraform output aiops_cloudwatch_dashboard_name
terraform output aiops_cloudwatch_alarm_names
terraform output cpu_sagemaker_endpoint_name
terraform output log_sagemaker_endpoint_name
```

Control-plane and endpoint outputs return `null` or `[]` when the related optional modules are disabled.

## Smoke Tests

After apply:

```bash
scripts/smoke_test.sh dev
```

Reports are written to:

```text
reports/smoke/dev.summary.txt
reports/smoke/dev.json
```

Synthetic anomaly validation is opt-in because it runs SSM commands on the workload:

```bash
ALLOW_SYNTHETIC_ANOMALY_TEST=true scripts/smoke_test.sh dev
```

## Jira And SNS Post-Apply Steps

If the control plane is enabled:

1. Populate the Jira secret in Secrets Manager out of band.
2. Confirm the SNS email subscription if `notification_email` is set.
3. Run smoke tests again.

Jira secret JSON:

```json
{
  "JIRA_API_URL": "https://example.atlassian.net",
  "JIRA_USER_EMAIL": "ops@example.com",
  "JIRA_API_TOKEN": "redacted"
}
```

## Cleanup

Destroy dev resources:

```bash
terraform plan -destroy -out=destroy.tfplan
terraform apply destroy.tfplan
```

Remove local generated artifacts:

```bash
scripts/cleanup_ephemeral.sh
```

## Troubleshooting

- `terraform validate` provider handshake error: remove `.terraform/`, rerun `terraform init`, and confirm the AWS provider binary matches the host architecture.
- No monitored instances: verify `Project=AIOPs` and `AnomalyMonitoring=enabled` tags.
- No log data: confirm the CloudWatch Agent is running on the EC2 instance.
- Lambda errors: inspect `/aws/lambda/<function-name>` and the CloudWatch dashboard.
- Remediation skipped: check SSM parameters, `dry_run`, instance tags, attempt count, and cooldown.
