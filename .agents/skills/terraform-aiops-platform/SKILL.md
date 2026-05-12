---
description: Use when designing, refactoring, or implementing the Terraform-only AWS infrastructure for the AIOps platform, including migration from the existing Terraform and SAM files.
---

# Terraform AIOps Platform Skill

## Goal
Help deliver the AIOps platform with Terraform as the single infrastructure deployment tool.

## Use this skill when
- Migrating `AIOPs_SAM/template.yaml` resources into Terraform.
- Refactoring `TERRAFORM_Code/main.tf` into senior Terraform modules.
- Adding SageMaker endpoint infrastructure.
- Creating environment-specific Terraform composition under `infra/envs/dev`, `infra/envs/stage`, or `infra/envs/prod`.
- Reviewing Terraform for production readiness.

## Required first steps
1. Read the current files:
   - `README.md`
   - `TERRAFORM_Code/main.tf`
   - `TERRAFORM_Code/userdata.sh`
   - `AIOPs_SAM/template.yaml`
   - `AIOPs_SAM/samconfig.toml`
2. Identify all AWS resources currently managed manually, by SAM, or by Terraform.
3. Create a migration map before writing code.

## Migration map format
Use this table before implementation:

| Current source | Current resource | Target Terraform module | Notes/Risks |
|---|---|---|---|
| SAM | Lambda function | `modules/lambda-function` | Package zip from Jenkins |
| SAM | DynamoDB table | `modules/dynamodb` | TTL enabled |
| SAM | SQS queue/DLQ | `modules/sqs` | Delay/grace period behavior |
| SAM | SNS topic/subscription | `modules/sns` | Email confirmation required |
| SAM | EventBridge schedule/bus | `modules/eventbridge` | Lambda trigger and audit events |
| Terraform | EC2 instance | `modules/ec2-workload` | Replace public SSH with SSM |
| Manual/SageMaker scripts | SageMaker endpoint | `modules/sagemaker-endpoint` | Artifact URI passed from Jenkins |

## Target Terraform modules
Create or maintain these modules:

```text
infra/modules/
├── networking/
├── iam/
├── ec2-workload/
├── sagemaker-endpoint/
├── lambda-function/
├── dynamodb/
├── sqs/
├── sns/
├── eventbridge/
├── ssm-parameters/
├── secrets-manager/
├── cloudwatch-observability/
└── aiops-control-plane/
```

## Design rules
- Use Terraform remote state with S3 and DynamoDB locking.
- Use one root module per environment.
- Pin AWS provider versions.
- Use variable validation for environment names, thresholds, endpoint names, log retention, and allowed CIDRs.
- Every AWS resource must include common tags:
  - `Project = "AIOps"`
  - `Environment = var.environment`
  - `ManagedBy = "Terraform"`
- Never create unencrypted persistence resources unless there is a documented exception.
- Avoid public SSH. Use SSM Session Manager.
- Do not hardcode credentials, AMI IDs, account IDs, emails, or endpoint names in modules.
- Use data sources for region/account identity when constructing ARNs.

## SageMaker Terraform pattern
Terraform should create:
- execution IAM role
- `aws_sagemaker_model`
- `aws_sagemaker_endpoint_configuration`
- `aws_sagemaker_endpoint`
- optional endpoint autoscaling resources
- CloudWatch alarms for endpoint invocation errors and latency

Terraform should not train the model. Jenkins trains/validates/uploads model artifacts and passes:
- `cpu_model_artifact_s3_uri`
- `log_model_artifact_s3_uri`
- `cpu_model_image_uri`
- `log_model_image_uri`
- `model_version`

## Lambda Terraform pattern
Terraform should receive a Lambda zip from Jenkins:
- local file path during plan/apply, or
- S3 bucket/key/version for a promoted artifact.

Preferred production input variables:
- `lambda_artifact_bucket`
- `lambda_artifact_key`
- `lambda_artifact_version`
- `lambda_source_code_hash`

Set environment variables for:
- CPU SageMaker endpoint name
- log SageMaker endpoint name
- DynamoDB table name
- SQS remediation queue URL
- SNS topic ARN
- EventBridge bus name
- SSM parameter paths
- Secrets Manager secret ARN
- feature flags and thresholds

## IAM rules
Use separate IAM roles for:
- EC2 instance profile
- Lambda execution
- SageMaker execution
- Jenkins deployment role

Scope Lambda permissions to:
- specific SageMaker endpoints
- specific DynamoDB table
- specific SQS queue/DLQ
- specific SNS topic
- specific EventBridge bus
- specific CloudWatch log groups
- EC2 remediation actions only for tagged monitored instances
- SSM commands only for tagged monitored instances/documents

## Acceptance checks
Before considering Terraform complete:
- `terraform fmt -check` passes.
- `terraform validate` passes.
- `tflint` passes or has documented exceptions.
- `checkov`/`tfsec` passes or has documented exceptions.
- `terraform plan` contains no unintended destructive changes.
- All modules have `variables.tf`, `outputs.tf`, and clear README notes.
- Outputs include values Jenkins smoke tests need.
