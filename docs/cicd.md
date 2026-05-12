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
4. `Python Install`
5. `Python Quality`
6. `Model Build and Validation`
7. `Package Lambda`
8. `Terraform Init`
   - validates the remote-state S3 bucket and DynamoDB lock table before init
9. `Terraform Quality`
10. `Terraform Plan`
11. `Approval`
12. `Terraform Apply`
13. `Smoke Tests`

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

## Terraform Plan and Apply

Jenkins always creates a saved plan:

```bash
terraform plan -input=false -out=tfplan -var-file=jenkins.auto.tfvars.json
terraform show -no-color tfplan > tfplan.txt
terraform show -json tfplan > tfplan.json
checkov -f tfplan.json --skip-check CKV_AWS_46,CKV_AWS_117,CKV_AWS_272,CKV2_AWS_57
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
