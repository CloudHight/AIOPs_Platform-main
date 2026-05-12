# AIOps Platform

Terraform and Jenkins driven AIOps platform for detecting CPU and Nginx/log anomalies on an EC2 workload, creating operational incidents, and safely scheduling remediation.

The repository preserves the original learning-oriented model code while adding a senior delivery structure:

- Terraform owns AWS infrastructure.
- Jenkins orchestrates validation, model training, Lambda packaging, Terraform plan/apply, and smoke tests.
- Python implements Lambda control-plane logic and ModelOps handoff tooling.
- AWS-native services provide metrics, logs, inference, alerting, incident state, and remediation orchestration.

## Architecture Flow

```text
Jenkins -> train/validate models -> S3 model artifacts
Jenkins -> package Lambda -> S3 Lambda artifact
Terraform -> EC2 workload, SageMaker endpoints, Lambda, DynamoDB, SQS, SNS, EventBridge, SSM, Secrets Manager, CloudWatch
EC2 -> CloudWatch CPU metrics and Nginx logs
EventBridge -> Lambda scheduled detection
Lambda -> CloudWatch + SageMaker -> DynamoDB anomaly record -> SNS + Jira -> delayed SQS remediation
SQS -> Lambda recheck -> safe remediation or skip
```

Detailed design: [docs/architecture.md](docs/architecture.md).

## AWS Services Used

- EC2, IAM instance profile, SSM Session Manager
- CloudWatch metrics, logs, dashboards, alarms, log metric filters
- SageMaker real-time endpoints
- Lambda
- DynamoDB
- SQS and DLQ
- SNS
- EventBridge schedule, custom event bus, and rules
- SSM Parameter Store
- Secrets Manager
- S3 and DynamoDB for Terraform backend
- Optional AWS Managed Grafana

## Repository Layout

```text
.
├── Jenkinsfile
├── docs/
├── infra/
│   ├── backend/
│   ├── jenkins/
│   ├── envs/{dev,stage,prod}/
│   └── modules/
├── lambda/
│   ├── src/aiops/
│   └── tests/
├── models/
├── scripts/
├── RCF_Model/
├── BERT_Model/
├── TERRAFORM_Code/
└── AIOPs_SAM/
```

Legacy folders remain for source model/training context. New delivery paths live under `infra/`, `lambda/`, `models/`, and `scripts/`.

## Prerequisites

Local or Jenkins agent tools:

- Python 3.9 or newer
- Terraform 1.6+
- AWS CLI v2
- `jq`
- `zip`
- Java for Jenkins/scanners
- `tflint`
- `checkov`

AWS prerequisites:

- AWS account and deploy role for each target environment
- S3 bucket for model artifacts
- S3 bucket for Lambda artifacts
- Terraform backend resources from `infra/backend`
- Jira credentials populated in Secrets Manager after Terraform creates the secret shell
- Confirmed SNS email subscription, if email notification is used

## Jenkins CI/CD

The repo includes a Jenkins controller bootstrap stack in `infra/jenkins` and the root [Jenkinsfile](Jenkinsfile).

Bootstrap order:

```text
infra/backend -> infra/jenkins -> Jenkinsfile deploys infra/envs/dev|stage|prod
```

The Jenkinsfile implements:

1. checkout and environment resolution
2. tooling preflight
3. Python install and quality checks
4. model build, validation, packaging, and upload
5. Lambda deterministic zip packaging and upload
6. Terraform init, fmt, validate, security scans, plan, approval, and apply
7. post-apply smoke tests

Branch mapping:

- `feature/*`: dev plan by default
- `develop`: dev
- `release/*`: stage with approval
- `main`: prod with approval

Details: [docs/cicd.md](docs/cicd.md).

## Terraform Deployment

Bootstrap backend once:

```bash
cd infra/backend
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform apply
```

Then configure the S3 backend blocks in `infra/envs/<env>/versions.tf`.

Plan an environment:

```bash
cd infra/envs/dev
terraform init
terraform fmt -check -recursive ../..
terraform validate
terraform plan -out=tfplan
```

Jenkins is the preferred apply path because it packages artifacts and archives the saved Terraform plan.

Deployment guide: [docs/deployment.md](docs/deployment.md).

## ModelOps Workflow

Jenkins runs:

```bash
scripts/train_cpu_model.sh
scripts/train_log_model.sh
scripts/package_model_artifacts.sh
scripts/upload_model_artifacts.sh
scripts/write_model_tfvars.sh infra/envs/dev/model-artifacts.auto.tfvars.json
```

Terraform consumes immutable artifact URIs and image URIs through `infra/modules/sagemaker-endpoint`.

Details: [docs/modelops.md](docs/modelops.md).

## Security

Key controls:

- no public SSH; use SSM Session Manager
- Jira credentials in Secrets Manager
- runtime flags and thresholds in SSM Parameter Store
- DynamoDB TTL and point-in-time recovery
- SQS DLQ and grace period
- tagged remediation guardrails: `Project=AIOPs` and `AnomalyMonitoring=enabled`
- scoped Lambda IAM for SageMaker, DynamoDB, SQS, SNS, EventBridge, SSM, logs, and EC2 remediation
- Terraform state backend supports S3 encryption and DynamoDB locking

Security guide: [docs/security.md](docs/security.md).

## Testing And Validation

Run unit tests:

```bash
PYTHONPATH=lambda/src python3 -m unittest discover -s lambda/tests
```

Run smoke tests after apply:

```bash
scripts/smoke_test.sh dev
```

Optional synthetic anomaly validation:

```bash
ALLOW_SYNTHETIC_ANOMALY_TEST=true scripts/smoke_test.sh dev
```

Validation checklist: [docs/operational-validation.md](docs/operational-validation.md).

## Cleanup

Destroy from the environment root only after reviewing state and dependencies:

```bash
cd infra/envs/dev
terraform plan -destroy -out=destroy.tfplan
terraform apply destroy.tfplan
```

Clean local generated files:

```bash
scripts/cleanup_ephemeral.sh
```

## Troubleshooting

- Terraform provider handshake failure locally: remove `.terraform/`, rerun `terraform init`, and confirm the provider binary matches host architecture.
- Lambda errors: inspect `/aws/lambda/<function>` logs and the CloudWatch dashboard.
- No anomalies: confirm EC2 tags, CloudWatch metrics/log ingestion, and SageMaker endpoint names.
- No Jira ticket: check Secrets Manager value shape and Jira API permissions.
- Remediation skipped: confirm SSM parameters, dry-run setting, EC2 tags, and remediation attempt count.

Runbook: [docs/operations-runbook.md](docs/operations-runbook.md).
