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

## Temporary Demo ALB

Stage supports an optional HTTP-only public ALB for demo validation:

```hcl
enable_public_http_alb = true
alb_allowed_http_cidrs = ["0.0.0.0/0"]
```

This exposes only the ALB on port 80. The workload instance still uses SSM for administration and receives HTTP from the ALB security group. Treat this as temporary demo exposure; production should use HTTPS, restricted CIDRs, and WAF where appropriate.

After apply, use:

```bash
terraform output workload_alb_url
```
