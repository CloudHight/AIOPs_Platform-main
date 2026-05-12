# Jenkins Controller Stack

Terraform root module for bootstrapping a Jenkins controller for the AIOps platform.

This stack is separate from `infra/envs/dev`, `infra/envs/stage`, and `infra/envs/prod` because Jenkins is the delivery system that deploys those environments.

## What It Creates

- EC2 Jenkins controller
- Jenkins home EBS volume
- IAM role and instance profile
- Jenkins deploy roles for `dev`, `stage`, and `prod`
- SSM Session Manager access
- optional port 8080 access for Jenkins UI
- Java, Jenkins, Git, Terraform, AWS CLI, Python, jq, zip, Docker, and Python model tooling

## Security Defaults

Defaults are intentionally conservative:

```hcl
associate_public_ip_address = false
allowed_jenkins_cidrs       = []
```

Use SSM Session Manager or private network access. If you need temporary browser access, set `associate_public_ip_address = true` and restrict `allowed_jenkins_cidrs` to your public IP CIDR.

No Jenkins admin password, AWS key, Jira token, or plugin secret is stored in Terraform.

## Deploy

```bash
cd infra/jenkins
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform plan -out=tfplan
terraform apply tfplan
```

Start an administration session through SSM:

```bash
terraform output -raw ssm_start_session_command
```

Run the printed command, then read the initial admin password inside the session:

```bash
sudo cat /var/lib/jenkins/secrets/initialAdminPassword
```

## Jenkins Credentials To Add

Create these Jenkins credentials after first login:

```text
aws-deploy-role-arn-dev
aws-deploy-role-arn-stage
aws-deploy-role-arn-prod
model-artifact-bucket
lambda-artifact-bucket
```

Use the created deploy role ARNs from:

```bash
terraform output jenkins_deploy_role_arns
```

Store each environment role ARN in the matching Jenkins credential:

```text
aws-deploy-role-arn-dev
aws-deploy-role-arn-stage
aws-deploy-role-arn-prod
```

By default this stack creates deploy roles for:

```hcl
deploy_role_environments = ["dev", "stage", "prod"]
```

Additional pre-existing deploy roles can still be allowed through `allowed_deploy_role_arns`.

The created deploy roles contain a broad but project-oriented Terraform deployment policy for the AWS services used by this platform. Tighten this policy before production use if your organization requires stricter environment or resource boundaries.

## SageMaker Training Note

This stack installs the tools needed to launch SageMaker training jobs from Jenkins, but it does not create a SageMaker Notebook instance. The repeatable path is:

```text
Jenkins -> SageMaker training/tuning job -> S3 model artifact -> Terraform SageMaker endpoint
```

The model scripts still need explicit SageMaker execution role support before they are fully Jenkins-safe outside a Notebook or Studio environment.
