# Infrastructure

Terraform infrastructure for the AIOps platform.

Terraform is the only tool that should create or update AWS resources for this project. Jenkins is the preferred delivery orchestrator because it builds artifacts, runs quality gates, produces a saved Terraform plan, applies that saved plan, and then runs smoke tests.

Local Terraform is still supported for backend bootstrap, Jenkins bootstrap, dev planning, troubleshooting, and controlled development applies.

## Layout

```text
infra/
├── backend/
│   └── One-time remote-state bootstrap: S3 state bucket, DynamoDB lock table, and KMS key.
├── jenkins/
│   └── Terraform root for the Jenkins controller that runs the root Jenkinsfile.
├── envs/
│   ├── dev/
│   │   └── Development/demo environment root.
│   ├── stage/
│   │   └── Release validation environment root.
│   └── prod/
│       └── Production environment root.
├── modules/
│   ├── aiops-control-plane/
│   ├── cloudwatch-observability/
│   ├── dynamodb/
│   ├── ec2-workload/
│   ├── eventbridge/
│   ├── iam/
│   ├── jenkins-controller/
│   ├── lambda-function/
│   ├── networking/
│   ├── sagemaker-endpoint/
│   ├── secrets-manager/
│   ├── sns/
│   ├── sqs/
│   └── ssm-parameters/
└── MIGRATION_MAP.md
```

## What Gets Provisioned

The environment roots compose the platform from reusable modules.

Always deployed in the app environments:

- monitored EC2 workload
- workload IAM role and instance profile
- workload security group
- Nginx access/error CloudWatch log groups
- CloudWatch Agent and SSM-enabled bootstrap
- required monitored-resource tags, including `AnomalyMonitoring=enabled`

Optional SageMaker layer:

- CPU RCF SageMaker model, endpoint configuration, and endpoint
- Nginx/log anomaly SageMaker model, endpoint configuration, and endpoint
- endpoint alarms and outputs consumed by the Lambda control plane

Optional AIOps control plane:

- Lambda anomaly processor and remediation handler
- DynamoDB anomaly/remediation table
- SQS remediation queue and DLQ
- SNS notification topic/subscription
- EventBridge schedule and event bus/rules
- SSM runtime parameters
- Secrets Manager Jira credential shell
- CloudWatch dashboard and alarms

Separate bootstrap stacks:

- `backend/` provisions remote-state infrastructure.
- `jenkins/` provisions the Jenkins controller EC2 instance and its supporting IAM/security resources.

## Provisioning Order

Use this order for a fresh AWS account or region:

1. Bootstrap Terraform remote state from `infra/backend`.
2. Enable the S3 backend blocks in `infra/envs/<env>/versions.tf`.
3. Bootstrap Jenkins from `infra/jenkins`.
4. Configure Jenkins plugins and credentials.
5. Let Jenkins build model/Lambda artifacts and deploy `infra/envs/dev`.
6. Promote to `stage` and `prod` through Jenkins with manual approval.
7. Run smoke tests and complete post-apply setup, such as Jira secret values and SNS email confirmation.

## Local Bootstrap Workflow

Local bootstrap is expected for the backend and Jenkins controller because Jenkins cannot deploy itself before it exists.

### Backend

```bash
cd infra/backend
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform plan -out=tfplan
terraform apply tfplan
```

Use the backend outputs to fill the commented backend blocks in:

```text
infra/envs/dev/versions.tf
infra/envs/stage/versions.tf
infra/envs/prod/versions.tf
```

Then initialize each environment with the remote backend:

```bash
terraform -chdir=infra/envs/dev init -migrate-state
```

Validate the backend from the same AWS identity that will run Terraform:

```bash
scripts/validate_terraform_backend.sh infra/envs/dev
```

Jenkins runs this validation before `terraform init`. A missing or unreachable
DynamoDB lock table is a backend bootstrap failure and should be fixed in
`infra/backend`; do not disable state locking in the pipeline.

### Jenkins Controller

```bash
cd infra/jenkins
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform plan -out=tfplan
terraform apply tfplan
```

The Jenkins stack defaults to no public UI exposure:

```hcl
associate_public_ip_address = false
allowed_jenkins_cidrs       = []
```

Use SSM Session Manager for administration:

```bash
terraform -chdir=infra/jenkins output -raw ssm_start_session_command
```

Run the printed command, then read the initial Jenkins password inside the instance:

```bash
sudo cat /var/lib/jenkins/secrets/initialAdminPassword
```

## Jenkins Provisioning Workflow

After Jenkins is bootstrapped, normal app environment delivery should run through the root `Jenkinsfile`.

Jenkins is responsible for:

- checking out the repo
- validating branch-to-environment mapping
- running Python tests and quality checks
- training/validating models when enabled
- uploading approved model artifacts to S3 immutable paths
- packaging the Lambda zip
- writing artifact tfvars for Terraform
- validating the remote-state backend bucket and DynamoDB lock table
- running `terraform fmt`, `terraform init`, `terraform validate`, and scanning
- creating and archiving a saved Terraform plan
- requiring approval for stage/prod applies
- applying only the saved plan
- running smoke tests after apply

Typical dev pipeline parameters:

```text
TARGET_ENV=dev
TRAIN_MODELS=true
APPLY=true
RUN_SMOKE_TESTS=true
```

Stage and production should be deployed only through Jenkins. The intended branch mapping is:

- `develop` or feature validation: `dev`
- `release/*`: `stage`
- `main`: `prod`

## Jenkins Credentials

Create these Jenkins secret text credentials after first login:

```text
aws-deploy-role-arn-dev
aws-deploy-role-arn-stage
aws-deploy-role-arn-prod
model-artifact-bucket
lambda-artifact-bucket
sagemaker-execution-role-arn
cpu-model-image-uri
log-model-image-uri
```

`infra/jenkins` creates deploy roles for `dev`, `stage`, and `prod` by default:

```hcl
create_deploy_roles      = true
deploy_role_environments = ["dev", "stage", "prod"]
```

After applying `infra/jenkins`, read the role ARNs and store them in the matching Jenkins credentials:

```bash
terraform -chdir=infra/jenkins output jenkins_deploy_role_arns
```

Additional pre-existing role ARNs can be added with `allowed_deploy_role_arns`.

The created deploy roles include permissions for Terraform-managed resources, S3 artifact upload/read, SageMaker operations, Lambda deployment, CloudWatch, EventBridge, SQS, SNS, DynamoDB, SSM, Secrets Manager, and scoped `iam:PassRole` for project roles. Tighten these policies before production if stricter account boundaries are required.

## Local Environment Workflow

Local environment planning is useful for development and review:

```bash
cd infra/envs/dev
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform fmt -check -recursive ../..
terraform validate
terraform plan -out=tfplan
```

For a local dev apply, review the saved plan first:

```bash
terraform apply tfplan
```

Avoid local applies for stage/prod. Use Jenkins so the plan, artifacts, approvals, and smoke-test results are tied to one pipeline run.

## Artifact Inputs

Terraform deploys infrastructure and consumes artifacts. It does not train models or build Lambda packages.

For local control-plane testing, package Lambda first:

```bash
scripts/package_lambda.sh
```

Then pass either a local package path:

```hcl
enable_aiops_control_plane = true
lambda_local_package_path  = "../../../dist/lambda/aiops-lambda.zip"
lambda_source_code_hash    = "<base64 sha256>"
```

Or the Jenkins/S3 artifact coordinates:

```hcl
lambda_artifact_bucket  = "<lambda-artifact-bucket>"
lambda_artifact_key     = "lambda/dev/<build-number>/aiops-lambda.zip"
lambda_source_code_hash = "<base64 sha256>"
```

For SageMaker endpoints, Jenkins should write model artifact variables after model validation:

```hcl
enable_sagemaker_endpoints = true
model_version              = "<git-sha-or-build-number>"
cpu_model_artifact_s3_uri  = "s3://<bucket>/models/cpu-rcf/<version>/model.tar.gz"
log_model_artifact_s3_uri  = "s3://<bucket>/models/nginx-bert/<version>/model.tar.gz"
cpu_model_image_uri        = "<sagemaker-cpu-image-uri>"
log_model_image_uri        = "<sagemaker-log-image-uri>"
```

The current model scripts still need explicit SageMaker execution role support before fully unattended Jenkins model training is reliable outside Notebook/Studio contexts.

## Post-Apply Steps

After the control plane is deployed:

1. Populate the Jira secret in Secrets Manager out of band.
2. Confirm the SNS email subscription if `notification_email` is configured.
3. Run smoke tests.
4. Review CloudWatch dashboards and alarms.
5. Keep remediation in dry-run until anomaly detection and alerting are validated.

Example Jira secret payload:

```json
{
  "JIRA_API_URL": "https://example.atlassian.net",
  "JIRA_USER_EMAIL": "ops@example.com",
  "JIRA_API_TOKEN": "replace-out-of-band"
}
```

## Quality Gates

Local checks:

```bash
terraform fmt -check -recursive infra
terraform -chdir=infra/envs/dev init
terraform -chdir=infra/envs/dev validate
terraform -chdir=infra/jenkins init
terraform -chdir=infra/jenkins validate
```

Jenkins runs IaC/security checks as required gates:

```bash
tflint --recursive
terraform show -json tfplan > tfplan.json
checkov -f tfplan.json --skip-check CKV_AWS_46,CKV_AWS_117,CKV_AWS_173,CKV_AWS_272,CKV2_AWS_57
scripts/secret_scan.sh
```

The pipeline runs Checkov against the saved plan for the resolved target environment. Full-repository IaC scans should run as a separate security review job so a dev deployment is not blocked by unrelated backend, Jenkins bootstrap, stage, or prod root modules.

The Checkov skips are reviewed project exceptions: EC2 user data is covered by secret scanning and contains no embedded credentials, Lambda is not VPC-attached because it calls AWS public service APIs, Lambda environment encryption is configured with a customer-managed KMS key but plan scans cannot always resolve same-plan key references, Lambda code signing is not yet part of the packaging contract, and Jira API token rotation is handled operationally because Atlassian token rotation is external to AWS.

## Smoke Testing

After apply:

```bash
scripts/smoke_test.sh dev
```

Smoke reports are written to:

```text
reports/smoke/dev.summary.txt
reports/smoke/dev.json
```

Synthetic anomaly testing is opt-in because it runs commands against the workload through SSM:

```bash
ALLOW_SYNTHETIC_ANOMALY_TEST=true scripts/smoke_test.sh dev
```

## Destroy Workflow

Destroy app environments from the environment root:

```bash
cd infra/envs/dev
terraform plan -destroy -out=destroy.tfplan
terraform apply destroy.tfplan
```

Destroy Jenkins only after app delivery is no longer needed:

```bash
cd infra/jenkins
terraform plan -destroy -out=destroy.tfplan
terraform apply destroy.tfplan
```

Keep `infra/backend` until all environment state is migrated or destroyed.

Clean generated local artifacts:

```bash
scripts/cleanup_ephemeral.sh
```

## Troubleshooting

- Terraform AWS provider handshake failure: remove the affected `.terraform/` directory, run `terraform init` again, and verify the provider binary architecture. If the local workstation still fails, validate on the Jenkins controller.
- Jenkins UI not reachable: confirm whether `associate_public_ip_address` is false, whether `allowed_jenkins_cidrs` is empty, and whether you are expected to use SSM or private networking.
- Jenkins cannot assume deploy role: verify `jenkins_deploy_role_arns`, any extra `allowed_deploy_role_arns`, the target role trust policy, and the Jenkins credential value for the environment.
- No monitored instances: verify workload tags include `Project=AIOPs` and `AnomalyMonitoring=enabled`.
- No CloudWatch log data: verify CloudWatch Agent and Nginx are running on the workload instance.
- SageMaker deployment fails: verify model artifact S3 URIs, container image URIs, SageMaker execution role, and `iam:PassRole`.
- Remediation does not run: verify SQS queue depth, DLQ alarms, SSM permissions, dry-run flags, and anomaly record status in DynamoDB.
