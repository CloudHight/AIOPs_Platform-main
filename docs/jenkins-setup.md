# Jenkins Setup

This repo includes Terraform to bootstrap a Jenkins controller for the AIOps platform.

## Why It Is Separate

Jenkins deploys `infra/envs/dev`, `infra/envs/stage`, and `infra/envs/prod`, so the controller must be created before those environments. The bootstrap stack lives in:

```text
infra/jenkins
```

Reusable implementation:

```text
infra/modules/jenkins-controller
```

## Deployment

```bash
cd infra/jenkins
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform plan -out=tfplan
terraform apply tfplan
```

The bootstrap example exposes the Jenkins UI publicly on port 8080:

```hcl
associate_public_ip_address = true
allowed_jenkins_cidrs       = ["0.0.0.0/0"]
```

This is intended for a demo controller. SSM Session Manager remains available for administration.

## Initial Login

If public UI access is enabled, get the URL:

```bash
terraform output -raw jenkins_url
```

Get the instance ID:

```bash
terraform output -raw jenkins_instance_id
```

Start an SSM session:

```bash
aws ssm start-session --target "$(terraform output -raw jenkins_instance_id)"
```

Read the initial admin password:

```bash
sudo cat /var/lib/jenkins/secrets/initialAdminPassword
```

## Installed Tools

The bootstrap installs:

- Jenkins LTS
- Java 17
- Git
- Terraform
- AWS CLI v2
- Python 3 and pip
- jq
- zip/unzip
- Docker
- baseline Python tools for Lambda/model workflows

## Required Jenkins Configuration

Install or confirm Jenkins plugins for:

- Pipeline
- Git
- Credentials Binding
- Timestamper
- AnsiColor
- JUnit

Create secret text credentials:

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

The Jenkins stack creates deploy roles for `dev`, `stage`, and `prod` by default. Read the ARNs with:

```bash
terraform output jenkins_deploy_role_arns
```

Store those ARNs in the matching Jenkins credentials:

```text
aws-deploy-role-arn-dev
aws-deploy-role-arn-stage
aws-deploy-role-arn-prod
```

Additional pre-existing deploy roles can still be listed in `allowed_deploy_role_arns`.

## Model Training Requirements

The controller has the tools needed to launch SageMaker jobs from `models/cpu-rcf` and `models/nginx-bert`. Store the SageMaker execution role ARN in the Jenkins `sagemaker-execution-role-arn` secret text credential so the model launchers do not rely on Notebook or Studio role discovery.

Required training-role permissions include:

- `sagemaker:CreateTrainingJob`
- `sagemaker:CreateHyperParameterTuningJob`
- `sagemaker:DescribeTrainingJob`
- `sagemaker:DescribeHyperParameterTuningJob`
- `sagemaker:StopTrainingJob`
- `iam:PassRole`
- S3 read/write for training data and model artifacts
- CloudWatch Logs write/read for training logs

Notebook or Studio runs are experimentation only. Repeatable delivery runs through Jenkins, which launches SageMaker jobs from `models/cpu-rcf/` and `models/nginx-bert/`.
