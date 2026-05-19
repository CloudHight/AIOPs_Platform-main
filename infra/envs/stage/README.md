# Stage Environment

Stage Terraform root module for release validation.

Jenkins maps `release/*` branches here and requires manual approval before apply.

## SageMaker Endpoints

For a full stage deployment, run Jenkins with:

```text
TRAIN_MODELS=true
DEPLOY_SAGEMAKER_ENDPOINTS=true
```

Jenkins writes `enable_sagemaker_endpoints=true` and validated CPU/log model artifact variables before Terraform planning. If endpoint deployment is disabled, this root module skips the SageMaker endpoint resources and the control plane uses the configured existing endpoint names.

To reuse a previously approved model version without retraining:

```text
TRAIN_MODELS=false
DEPLOY_SAGEMAKER_ENDPOINTS=true
USE_EXISTING_MODEL_ARTIFACTS=true
APPROVED_MODEL_VERSION=release-v1.0.0-26
```

Jenkins verifies the model artifacts, metadata, and evaluation files exist for both model families before planning.

The default log endpoint instance type is `ml.g5.xlarge`. AWS rejects endpoint configuration KMS keys for some GPU/NVMe instance families, including `g5`, so this root automatically disables endpoint storage KMS only for those log endpoint instance types. Other supported storage surfaces remain KMS-backed.

## Jira Secret Name

The control plane defaults the Jira secret name to an account-scoped value:

```text
aiops-jira-credentials-stage-<aws-account-id>
```

This avoids re-apply failures when an older stage secret name is still scheduled for deletion in Secrets Manager. Populate the created secret value out of band after apply.

## Temporary Demo Access

Stage exposes the workload instance directly over HTTP for temporary demo validation:

```hcl
workload_associate_public_ip = true
allowed_http_cidrs           = ["0.0.0.0/0"]
```

This exposes only port 80 on the workload instance. Administration still uses SSM Session Manager; SSH remains closed. Treat this as temporary demo exposure. Production should use HTTPS, restricted CIDRs, and a hardened load balancer or private access path.

After apply, use:

```bash
terraform output workload_public_url
```
