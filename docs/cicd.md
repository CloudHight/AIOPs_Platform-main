# Jenkins CI/CD

This repo is delivered by Jenkins. Jenkins orchestrates validation, model artifact creation, Lambda packaging, Terraform plan/apply, and smoke testing. Terraform remains the only tool that creates or updates AWS infrastructure.

The Jenkins controller itself can be bootstrapped from `infra/jenkins`. That stack is intentionally separate from `infra/envs/*` because Jenkins deploys those environments.

## Branch Mapping

| Branch | Environment | Apply behavior |
|---|---|---|
| `feature/*` | `dev` | Plan by default; apply only when `APPLY=true` |
| `develop` | `dev` | Can apply without manual approval |
| `release/*` | `stage` | Manual approval required |
| `main` | `prod` | Manual approval required |

The `TARGET_ENV` parameter can override automatic mapping, but the Jenkinsfile blocks unsafe promotion paths. Production applies are only allowed from `main`.

## Jenkins Parameters

- `TARGET_ENV`: `auto`, `dev`, `stage`, or `prod`.
- `APPLY`: applies the saved Terraform plan when enabled.
- `TRAIN_MODELS`: runs the CPU/log model build, packaging, upload, and Terraform handoff flow.
- `DEPLOY_SAGEMAKER_ENDPOINTS`: deploys Terraform-managed SageMaker endpoints from the model handoff. Leave enabled for full AIOps deployments; disable only when the Lambda should use pre-existing endpoint names.
- `USE_EXISTING_MODEL_ARTIFACTS`: skips model training and deploys a previously approved model version from the artifact bucket.
- `APPROVED_MODEL_VERSION`: required when `USE_EXISTING_MODEL_ARTIFACTS=true`; must exist for both `cpu-rcf` and `nginx-bert`.
- `RUN_SMOKE_TESTS`: runs smoke tests after apply.

## Required Credentials

Create these Jenkins credentials as secret text values:

- `aws-deploy-role-arn-dev`
- `aws-deploy-role-arn-stage`
- `aws-deploy-role-arn-prod`
- `model-artifact-bucket`
- `lambda-artifact-bucket`
- `sagemaker-execution-role-arn`
- `cpu-model-image-uri`
- `log-model-image-uri`

Optional credentials for notification integrations can be added later:

- `slack-webhook`
- environment-specific Jira test secret ARN if smoke tests need a dedicated test project

Do not store AWS access keys, SageMaker execution role ARNs, Jira tokens, Docker credentials, `.tfvars` secrets, or state credentials in this repository.

## Required Jenkins Agent Tools

The agent needs:

- Python 3.12 or newer
- Terraform
- AWS CLI v2
- `jq`
- `zip`
- Java, for Jenkins and scanner tooling
- `tflint`
- `tfsec`
- `checkov`
- `gitleaks` preferred; standard `grep` fallback is supported

The pipeline installs Python quality/model tools into a fresh `.venv` and Checkov into a separate fresh `.iac-venv` on every run so stale packages and IaC scanner dependencies cannot downgrade SageMaker/runtime dependencies. Python 3.12+ is required because the audited AWS SDK dependency graph resolves to patched `urllib3` 2.x only on supported modern runtimes.

The `infra/jenkins` bootstrap installs the baseline tools on the controller. Production teams may still prefer separate ephemeral agents for heavy model training and Terraform execution.

## SageMaker Training Prerequisite

The current RCF and BERT training scripts still use SageMaker SDK role discovery in places. To run them from Jenkins reliably, the scripts should be refactored to accept an explicit SageMaker execution role ARN and S3 output prefix. The Jenkins controller stack provides tooling and IAM hooks for role assumption, but the deploy/training roles must include SageMaker, S3, CloudWatch Logs, and `iam:PassRole` permissions.

## Pipeline Stages

1. `Checkout`
2. `Resolve Environment`
3. `Tooling Preflight`
4. `Secret Scan`
5. `Python Install`
6. `Python Quality`
7. `Model Build and Validation`
8. `Use Existing Model Artifacts`
   - runs only when `USE_EXISTING_MODEL_ARTIFACTS=true`
   - verifies `model.tar.gz`, `metadata.json`, and `evaluation.json` exist for both models before writing the Terraform handoff
9. `Package Lambda`
10. `Validate Terraform Handoff`
   - verifies Jenkins artifact variables are present
   - when `DEPLOY_SAGEMAKER_ENDPOINTS=true`, verifies CPU/log model artifact URIs and image URIs are present before planning
11. `Terraform Init`
   - validates the remote-state S3 bucket and DynamoDB lock table before init
12. `Terraform Quality`
   - runs `terraform fmt`, `terraform validate`, `tflint`, and `tfsec`
13. `Terraform Plan`
   - runs Checkov against the saved Terraform plan
14. `Approval`
15. `Terraform Apply`
16. `Smoke Tests`

## Artifact Flow

Model artifacts are published to immutable S3 prefixes:

```text
s3://<model-artifact-bucket>/models/<model-name>/<model-version>/model.tar.gz
s3://<model-artifact-bucket>/models/<model-name>/<model-version>/metadata.json
s3://<model-artifact-bucket>/models/<model-name>/<model-version>/evaluation.json
```

The model handoff writes:

```text
infra/envs/<env>/model-artifacts.auto.tfvars.json
```

Lambda artifacts are packaged as:

```text
dist/lambda/aiops-lambda.zip
dist/lambda/aiops-lambda.zip.sha256
dist/lambda/aiops-lambda.zip.base64sha256
```

Jenkins uploads the zip to:

```text
s3://<lambda-artifact-bucket>/lambda/<env>/<build-number>/aiops-lambda.zip
```

It then writes `infra/envs/<env>/jenkins.auto.tfvars.json` with the Lambda artifact reference and source hash.

The same file also carries the endpoint deployment switch:

```json
{
  "enable_aiops_control_plane": true,
  "enable_sagemaker_endpoints": true
}
```

When `DEPLOY_SAGEMAKER_ENDPOINTS=true`, Jenkins requires either `TRAIN_MODELS=true` or `USE_EXISTING_MODEL_ARTIFACTS=true`. Fresh training writes the handoff from the current build. Existing-artifact deployment regenerates the handoff from the approved version in S3 after verifying both models have `model.tar.gz`, `metadata.json`, and `evaluation.json`. This prevents Terraform from silently planning with `enable_sagemaker_endpoints=false` or with stale local artifact values.

Approved existing artifact deployment parameters:

```text
TRAIN_MODELS=false
DEPLOY_SAGEMAKER_ENDPOINTS=true
USE_EXISTING_MODEL_ARTIFACTS=true
APPROVED_MODEL_VERSION=release-v1.0.0-26
```

## Terraform Plan and Apply

Jenkins always creates a saved plan:

```bash
terraform plan -input=false -out=tfplan -var-file=jenkins.auto.tfvars.json
terraform show -no-color tfplan > tfplan.txt
terraform show -json tfplan > tfplan.json
tfsec . --minimum-severity HIGH --exclude-downloaded-modules --exclude aws-ec2-no-public-ingress-sgr,aws-ec2-no-public-egress-sgr --format json --out ../../../reports/tfsec-<env>.json
CHECKOV_SKIPS="CKV_AWS_46,CKV_AWS_98,CKV_AWS_117,CKV_AWS_173,CKV_AWS_272,CKV2_AWS_57"
if [ "${TARGET_ENV_RESOLVED}" = "stage" ]; then
  CHECKOV_SKIPS="${CHECKOV_SKIPS},CKV_AWS_88,CKV_AWS_260"
fi
checkov -f tfplan.json --skip-check "${CHECKOV_SKIPS}"
```

Apply uses the saved plan only:

```bash
terraform apply -input=false tfplan
```

`stage` and `prod` applies require an approval step.

## Smoke Tests

`scripts/smoke_test.sh <env>` validates:

- Terraform outputs are readable
- monitored EC2 instance exists with `AnomalyMonitoring=enabled` and `Project=AIOPs`
- CloudWatch CPU metrics are readable
- Nginx log groups are reachable
- SageMaker endpoints respond when deployed
- Lambda test invocation succeeds when the control plane is deployed
- DynamoDB, SQS, EventBridge, CloudWatch dashboard, and alarms exist when deployed

Smoke reports are written under:

```text
reports/smoke/
```

Optional synthetic anomaly checks can be enabled only for approved dev/stage runs:

```bash
ALLOW_SYNTHETIC_ANOMALY_TEST=true scripts/smoke_test.sh dev
```

## Failure Handling

Failed pipelines archive reports and Terraform plan output. Do not re-run apply by hand from a modified working directory. Re-run the pipeline so Jenkins produces a fresh plan tied to the current commit, artifacts, and build number.
