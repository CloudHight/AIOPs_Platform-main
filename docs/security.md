# Security

This project is designed to demonstrate a safer AIOps delivery path. It is not a substitute for an account-level security review, penetration test, or production change-management process.

## Secrets

Do not commit:

- AWS access keys
- Jira API tokens
- Docker registry passwords
- private keys
- `.tfvars` files containing secret values
- Terraform state
- generated Lambda or model artifacts

Jira credentials are stored in Secrets Manager. Terraform creates the secret shell; operators populate the value out of band.

Expected JSON shape:

```json
{
  "JIRA_API_URL": "https://example.atlassian.net",
  "JIRA_USER_EMAIL": "ops@example.com",
  "JIRA_API_TOKEN": "redacted"
}
```

## Network Access

The EC2 workload module does not allow public SSH. Operators should use SSM Session Manager.

The dev example allows public HTTP by default for demo access:

```hcl
allowed_http_cidrs = ["0.0.0.0/0"]
```

For stage/prod, keep `allowed_http_cidrs = []` or restrict it to approved CIDRs.

## IAM Guardrails

Lambda permissions are scoped by resource where practical:

- SageMaker invoke access is limited to configured endpoint ARNs.
- DynamoDB access is limited to the anomaly table and indexes.
- SNS publish is limited to the notification topic.
- SQS access is limited to the processing queue and DLQ.
- EventBridge publish is limited to the custom event bus.
- Secrets Manager read is limited to the Jira secret ARN.
- EC2 reboot and SSM command actions require tags:
  - `Project=AIOPs`
  - `AnomalyMonitoring=enabled`

Jenkins assumes environment-specific AWS deploy roles. Do not place static AWS keys in the Jenkinsfile.

## Runtime Safety

Auto-remediation is disabled by default:

```text
AutoRemediationEnabled=false
DryRun=true
MaxRemediationAttempts=1
```

These values are stored in SSM Parameter Store under:

```text
/AnomalyDetection/<environment>/
```

Only enable remediation after smoke tests, dashboard review, and operational approval.

## Encryption And State

Backend module creates:

- S3 bucket for Terraform state
- DynamoDB lock table
- KMS key for state encryption

Service modules accept KMS key inputs where supported. DynamoDB, SQS, SNS, Secrets Manager, and log storage should use KMS in production accounts.

## CI/CD Security Gates

Jenkins runs:

- Python compile checks
- unit tests
- `bandit`
- `pip-audit`
- secret scanning with `gitleaks` when installed, or the repo fallback scanner
- `terraform fmt`
- `terraform validate`
- `tflint`
- `tfsec`
- `checkov`

These gates are expected to fail the pipeline unless an exception is explicitly documented and reviewed.

## Credential Rotation

Before production use:

1. Rotate any credentials that were ever exposed in Git history.
2. Enable repository secret scanning.
3. Rotate Jira API tokens periodically.
4. Review Jenkins credential access.
5. Enable CloudTrail and GuardDuty in the AWS account.

## Security Findings

Historical findings and remediation notes are tracked in:

```text
SECURITY_FINDINGS.md
```
