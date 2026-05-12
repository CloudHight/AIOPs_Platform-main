# Deployment

Use Jenkins for normal delivery. Use local Terraform only for development plans, backend bootstrap, and emergency inspection.

## Deployment Order

1. Bootstrap Terraform backend.
2. Bootstrap Jenkins controller.
3. Configure environment backend blocks.
4. Configure Jenkins credentials.
5. Run Jenkins with `TRAIN_MODELS=true`.
6. Review archived Terraform plan.
7. Apply through Jenkins.
8. Run smoke tests and review dashboard/alarms.
9. Populate Jira secret value and confirm SNS email subscription if needed.

## Backend Bootstrap

Create remote-state resources once:

```bash
cd infra/backend
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform plan -out=tfplan
terraform apply tfplan
```

Outputs include the state bucket, lock table, and KMS key. Use those values to fill the commented backend blocks in:

```text
infra/envs/dev/versions.tf
infra/envs/stage/versions.tf
infra/envs/prod/versions.tf
```

Then run:

```bash
terraform -chdir=infra/envs/dev init -migrate-state
```

## Jenkins Bootstrap

Provision the Jenkins controller from a separate Terraform root:

```bash
cd infra/jenkins
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform plan -out=tfplan
terraform apply tfplan
```

The Jenkins stack creates an EC2 controller, Jenkins home EBS volume, instance profile, security group, and tooling needed by the pipeline. Defaults do not expose the Jenkins UI publicly.

Start an administration session through SSM:

```bash
terraform output -raw ssm_start_session_command
```

Run the printed command and then read the initial admin password inside the session:

```bash
sudo cat /var/lib/jenkins/secrets/initialAdminPassword
```

## Jenkins Credentials

Create these Jenkins secret text credentials:

```text
aws-deploy-role-arn-dev
aws-deploy-role-arn-stage
aws-deploy-role-arn-prod
model-artifact-bucket
lambda-artifact-bucket
```

The Jenkins bootstrap stack creates deploy roles for `dev`, `stage`, and `prod` by default. Store the output role ARNs in the matching Jenkins credentials:

```bash
terraform -chdir=infra/jenkins output jenkins_deploy_role_arns
```

The deploy roles allow Terraform to manage the AWS resources in the target environment and allow Jenkins to upload Lambda/model artifacts. Tighten the generated policy before production if your account requires stricter boundaries.

## Dev Deployment

Typical Jenkins parameters:

```text
TARGET_ENV=dev
APPLY=true
TRAIN_MODELS=true
RUN_SMOKE_TESTS=true
```

Local plan-only workflow:

```bash
scripts/package_lambda.sh
cd infra/envs/dev
terraform init
terraform fmt -check -recursive ../..
terraform validate
terraform plan -out=tfplan
```

For local control-plane plans, pass a Lambda artifact path:

```bash
terraform plan \
  -var='enable_aiops_control_plane=true' \
  -var='lambda_local_package_path=../../../dist/lambda/aiops-lambda.zip' \
  -out=tfplan
```

## Stage And Prod Deployment

Jenkins maps:

- `release/*` to `stage`
- `main` to `prod`

Both require manual approval before apply. Do not apply stage/prod plans from a developer workstation.

## Required Post-Apply Actions

Populate Jira credentials after Terraform creates the secret shell:

```bash
aws secretsmanager put-secret-value \
  --secret-id "$(terraform -chdir=infra/envs/dev output -raw jira_credentials_secret_arn 2>/dev/null || true)" \
  --secret-string '{
    "JIRA_API_URL": "https://example.atlassian.net",
    "JIRA_USER_EMAIL": "ops@example.com",
    "JIRA_API_TOKEN": "replace-out-of-band"
  }'
```

If SNS email is configured, confirm the subscription from the mailbox before expecting alerts.

## Smoke Test

```bash
scripts/smoke_test.sh dev
```

Reports:

```text
reports/smoke/dev.summary.txt
reports/smoke/dev.json
```

Synthetic validation is opt-in:

```bash
ALLOW_SYNTHETIC_ANOMALY_TEST=true scripts/smoke_test.sh dev
```

## Destroy

Destroy from the environment root:

```bash
cd infra/envs/dev
terraform plan -destroy -out=destroy.tfplan
terraform apply destroy.tfplan
```

Clean local generated artifacts:

```bash
scripts/cleanup_ephemeral.sh
```

## Known Local Validation Issue

This workspace has repeatedly shown a local Terraform AWS provider plugin handshake failure for `hashicorp/aws v5.100.0` on `darwin_amd64`. If this happens:

```bash
rm -rf infra/envs/dev/.terraform
terraform -chdir=infra/envs/dev init
terraform -chdir=infra/envs/dev validate
```

If it persists, verify the provider binary architecture and run validation on the Jenkins agent.
