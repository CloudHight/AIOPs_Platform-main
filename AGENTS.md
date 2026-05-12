# CLAUDE.md — AIOps Platform Senior Delivery Guide

## Project mission
Deliver `CloudHight/AIOPs_Platform` as a production-grade AIOps platform using:

- **Terraform as the single infrastructure-as-code tool** for AWS resource deployment.
- **Jenkins as the CI/CD orchestrator** for validation, model training/packaging, Lambda packaging, Terraform plan/apply, smoke tests, and controlled release promotion.
- **Python for ML/model workflows and Lambda runtime logic**.
- **AWS-native services** for monitoring, inference, alerting, incident creation, and remediation.

The current repo is a learning-oriented implementation split across SageMaker scripts, Terraform EC2 provisioning, and AWS SAM. The target state is a senior-level implementation where Jenkins drives the delivery workflow and Terraform owns the deployable AWS resources.

## Current repo context
Always inspect these areas before making changes:

- `README.md` — current deployment order and project description.
- `RCF_Model/` — CPU anomaly model workflow using SageMaker Random Cut Forest.
- `BERT_Model/` — Nginx/log anomaly classifier workflow.
- `TERRAFORM_Code/` — current EC2 workload provisioning and `userdata.sh`.
- `AIOPs_SAM/` — current Lambda orchestration code and SAM template to be migrated into Terraform.
- `test_commands.txt` — existing manual validation commands.

## Target architecture
Terraform should deploy and manage:

1. **Foundation**
   - S3 bucket for Terraform remote state.
   - DynamoDB lock table.
   - KMS keys for state, logs, DynamoDB, SQS, SNS, Secrets Manager, and optional artifact encryption.
   - IAM roles and least-privilege policies.

2. **Application workload**
   - EC2 instance or Auto Scaling Group for the monitored workload.
   - Instance profile with SSM and CloudWatch permissions.
   - Security groups with no public SSH.
   - Nginx, Docker/ECR application container, and CloudWatch Agent bootstrap.
   - Required tag: `AnomalyMonitoring=enabled`.

3. **Machine learning inference**
   - SageMaker execution role.
   - S3 model artifact bucket/prefixes.
   - SageMaker model resources.
   - Endpoint configurations.
   - SageMaker endpoints for CPU and log anomaly detection.

4. **AIOps control plane**
   - Lambda function for detection, alerting, incident creation, and remediation scheduling.
   - Lambda execution role with scoped IAM permissions.
   - DynamoDB table for anomaly records, deduplication, TTL, and remediation status.
   - SQS queue and DLQ for grace-period remediation.
   - SNS topic and confirmed email subscriptions.
   - EventBridge schedule, event bus, and rules.
   - SSM Parameters for runtime thresholds and feature flags.
   - Secrets Manager for Jira URL, user email, and API token.

5. **Observability**
   - CloudWatch log groups with retention.
   - CloudWatch dashboards.
   - CloudWatch alarms for Lambda errors, SageMaker invocation errors, SQS DLQ depth, and remediation failures.
   - Optional Managed Grafana only if the module is complete and tested.

## Repository target layout
Prefer migrating toward this structure:

```text
.
├── CLAUDE.md
├── Jenkinsfile
├── Makefile
├── README.md
├── docs/
│   ├── architecture.md
│   ├── deployment.md
│   ├── operations-runbook.md
│   ├── security.md
│   └── project-defense.md
├── infra/
│   ├── backend/
│   ├── envs/
│   │   ├── dev/
│   │   ├── stage/
│   │   └── prod/
│   └── modules/
│       ├── aiops-control-plane/
│       ├── cloudwatch-observability/
│       ├── dynamodb/
│       ├── ec2-workload/
│       ├── eventbridge/
│       ├── iam/
│       ├── lambda-function/
│       ├── networking/
│       ├── sagemaker-endpoint/
│       ├── secrets-manager/
│       ├── sns/
│       ├── sqs/
│       └── ssm-parameters/
├── lambda/
│   ├── src/aiops/
│   │   ├── __init__.py
│   │   ├── handler.py
│   │   ├── config.py
│   │   ├── discovery.py
│   │   ├── metrics_reader.py
│   │   ├── logs_reader.py
│   │   ├── inference.py
│   │   ├── anomaly_store.py
│   │   ├── alerting.py
│   │   ├── jira_client.py
│   │   ├── remediation.py
│   │   └── events.py
│   ├── tests/
│   ├── requirements.txt
│   └── pyproject.toml
├── models/
│   ├── cpu-rcf/
│   └── nginx-bert/
├── scripts/
│   ├── package_lambda.sh
│   ├── train_cpu_model.sh
│   ├── train_log_model.sh
│   ├── upload_model_artifacts.sh
│   ├── smoke_test.sh
│   └── cleanup_ephemeral.sh
└── .claude/skills/
```

## Senior delivery principles
Follow these rules consistently:

- Terraform owns AWS resource lifecycle. Do not keep SAM or manual console deployment as the final delivery path.
- Jenkins orchestrates CI/CD. Terraform must not be abused as a model-training engine.
- Model training, validation, packaging, and artifact upload happen before Terraform creates or updates SageMaker endpoints.
- Never commit secrets, Docker credentials, Jira tokens, private keys, `.tfvars` containing sensitive values, or generated state files.
- Prefer ECR and IAM-based authentication over Docker Hub credentials in user data.
- Prefer SSM Session Manager over SSH. Do not allow `0.0.0.0/0` SSH ingress.
- Use least-privilege IAM, scoped ARNs, resource tags, and conditions wherever practical.
- Use encrypted storage, explicit log retention, and lifecycle policies.
- Implement idempotency for alerting, Jira ticket creation, and remediation.
- Add tests before large refactors when possible.
- Preserve the existing learning goal, but raise implementation quality to senior/cloud-production standards.

## Jenkins delivery contract
The root `Jenkinsfile` should implement these stages:

1. `Checkout`
2. `Preflight`
   - Print tool versions.
   - Validate branch/environment mapping.
   - Ensure required Jenkins credentials exist.
3. `Python Quality`
   - Install dependencies in virtual environment.
   - Run formatting/linting/type checks where configured.
   - Run unit tests for Lambda and model utility code.
4. `Model Build and Validation`
   - Generate/train CPU model.
   - Generate/train log anomaly model.
   - Validate model thresholds and inference contracts.
   - Upload approved artifacts to S3 with immutable version paths.
5. `Lambda Package`
   - Package Lambda source into a deterministic zip artifact.
   - Publish package to S3 or pass local path into Terraform.
6. `Terraform Quality`
   - `terraform fmt -check`
   - `terraform init -backend-config=...`
   - `terraform validate`
   - `tflint`
   - `checkov` or `tfsec`
7. `Terraform Plan`
   - Generate a saved plan file.
   - Archive the plan output.
8. `Approval`
   - Required for `stage` and `prod` applies.
9. `Terraform Apply`
   - Apply the saved plan only.
10. `Smoke Tests`
    - Confirm EC2 instance tag discovery.
    - Confirm CloudWatch metrics/log ingestion.
    - Invoke Lambda test event.
    - Call SageMaker endpoints with sample CPU/log payloads.
    - Confirm DynamoDB write, SNS/SQS/EventBridge integration, and Jira dry-run or test-project ticket creation.
11. `Post Actions`
    - Publish test reports.
    - Archive artifacts.
    - Notify Slack/email.

## Terraform conventions
- Use modules under `infra/modules/`.
- Use environment-specific composition under `infra/envs/<env>/`.
- Use remote state with S3 and DynamoDB locking.
- Use pinned provider versions.
- Use explicit variable validation.
- Use outputs for endpoint names, Lambda names, dashboard URLs, DynamoDB table name, SQS queue URL, SNS topic ARN, and monitored workload identifiers.
- Use `for_each` where multiple alarms, parameters, policies, or log groups are generated.
- Avoid `count` when stable resource addressing matters.
- Use lifecycle rules deliberately; do not hide destructive changes with broad `ignore_changes`.

## Lambda/Python conventions
- Break the existing monolithic Lambda into testable modules.
- Use structured JSON logging.
- Use typed config loading from environment variables and SSM Parameter Store.
- Cache SSM/runtime configuration safely within Lambda execution context.
- Separate pure business logic from boto3 calls.
- Make AWS clients injectable for tests.
- Use explicit error classes for inference failure, missing metrics, Jira failure, and remediation failure.
- Do not swallow exceptions without logging context.
- Add unit tests using stubbed AWS clients or `botocore.stub.Stubber`.

## ModelOps conventions
- Store model artifacts under immutable S3 prefixes, for example:
  `s3://<artifact-bucket>/models/<model-name>/<git-sha-or-build-number>/model.tar.gz`
- Store metadata with each artifact:
  - git commit
  - Jenkins build number
  - training data version
  - evaluation metrics
  - chosen threshold
  - container image URI
- Terraform consumes approved artifact URIs and creates/updates SageMaker model and endpoint resources.
- Do not deploy a model if validation fails or the expected inference payload contract changes without corresponding Lambda changes.

## Security requirements
- Rotate and remove any exposed credentials from Git history before production use.
- Store Jira credentials in Secrets Manager.
- Store thresholds and non-secret runtime config in SSM Parameter Store.
- Use KMS encryption for state, logs, DynamoDB, SQS, SNS, and Secrets Manager where possible.
- Restrict SageMaker invoke permissions to the specific endpoint ARNs.
- Restrict EC2 remediation permissions to tagged monitored resources.
- Add IAM conditions using tags such as `Project=AIOps` and `AnomalyMonitoring=enabled`.
- Run secret scanning and IaC security scanning in Jenkins.

## Definition of done
A change is not complete until:

- `terraform fmt`, `terraform validate`, linting, security scanning, and tests pass.
- Jenkins produces and archives a Terraform plan.
- The applied environment can detect CPU/log anomalies end-to-end.
- Alerts, DynamoDB records, EventBridge events, and remediation queue behavior are validated.
- Rollback or cleanup steps are documented.
- Documentation is updated for any new module, variable, Jenkins credential, or operational runbook change.
