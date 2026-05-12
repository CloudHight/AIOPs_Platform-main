---
description: Use when reviewing or improving security for the AIOps platform, including IAM, secrets, network exposure, Terraform scanning, Jenkins credentials, and remediation guardrails.
---

# Security Hardening Skill

## Goal
Raise the AIOps platform from demo security to senior production-grade security.

## Use this skill when
- Reviewing Terraform IAM policies.
- Fixing hardcoded secrets or Docker credentials.
- Replacing SSH access with SSM Session Manager.
- Adding encryption, KMS, log retention, or security scanning.
- Securing Jenkins credentials and AWS access.
- Constraining remediation actions.

## Immediate high-priority fixes
Check for and fix these first:

1. Hardcoded Docker credentials in user data or scripts.
2. SSH ingress from `0.0.0.0/0`.
3. Broad IAM actions with `Resource = "*"`.
4. Secrets in `.tfvars`, Jenkinsfile, shell scripts, notebooks, or README examples.
5. Unencrypted S3, DynamoDB, SQS, SNS, Secrets Manager, or CloudWatch resources.
6. Missing log retention policies.
7. Terraform state stored locally or unencrypted.

## Credential handling rules
- Use ECR and IAM auth for pulling containers where possible.
- Use Secrets Manager for Jira credentials.
- Use SSM Parameter Store for non-secret runtime config.
- Use Jenkins credentials binding for deployment role ARNs and environment-specific values.
- Never print secrets in Jenkins logs.
- Mask sensitive command output.
- Rotate any credential that has ever been committed.

## IAM least-privilege rules
Create separate roles for:

- Jenkins deployment
- EC2 instance profile
- Lambda execution
- SageMaker execution

Lambda permissions should be scoped to:

- exact DynamoDB table ARN and indexes
- exact SQS queue/DLQ ARNs
- exact SNS topic ARN
- exact EventBridge bus/rule ARNs
- exact Secrets Manager secret ARN
- exact SSM parameter path
- exact SageMaker endpoint ARNs
- EC2/SSM remediation only for instances with required tags

Use IAM conditions where possible:

```json
{
  "StringEquals": {
    "aws:ResourceTag/Project": "AIOps",
    "aws:ResourceTag/AnomalyMonitoring": "enabled"
  }
}
```

## Network security rules
- Do not expose SSH publicly.
- Prefer SSM Session Manager.
- Restrict HTTP/HTTPS access based on the demo/production requirement.
- For production, place workload behind ALB/WAF where appropriate.
- Use VPC endpoints for private access to SSM, CloudWatch Logs, S3, ECR, Secrets Manager, and SQS/SNS if the design requires private networking.

## Encryption rules
- S3 artifact and state buckets: SSE-KMS.
- DynamoDB anomaly table: KMS encryption where supported/required.
- SQS queues: KMS encryption.
- SNS topics: KMS encryption.
- Secrets Manager: KMS key.
- CloudWatch log groups: KMS key if required by compliance.

## Jenkins security gates
Add these checks:

- Secret scanning: `gitleaks` or equivalent.
- Terraform static analysis: `checkov`, `tfsec`, or equivalent.
- Terraform linting: `tflint`.
- Dependency vulnerability scan where practical.
- Block deployment on high/critical findings unless an exception file is reviewed and committed.

## Remediation safety guardrails
Automated remediation must:

- Be disabled by default in prod until explicitly enabled.
- Use SQS grace period before action.
- Re-check anomaly state before executing action.
- Limit repeated remediation attempts per instance/anomaly type.
- Record all actions in DynamoDB and EventBridge.
- Never execute arbitrary SSM commands from untrusted input.

## Acceptance criteria
Security hardening is complete when:

- No secrets are present in source code.
- Public SSH is removed.
- IAM policies are scoped and reviewed.
- Jenkins security gates run automatically.
- State and important data stores are encrypted.
- Remediation actions are safe, auditable, and reversible where possible.
