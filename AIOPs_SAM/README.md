# AIOPs_SAM Legacy Reference

This folder is retained as read-only migration reference only. Do not use it to deploy the AIOps platform.

The active deployment path is Terraform and Jenkins:

```text
Jenkinsfile -> scripts/package_lambda.sh -> lambda/src/aiops -> infra/modules -> infra/envs/<env>
```

The SAM Lambda behavior and infrastructure resources have been compared against the Terraform/Lambda path in [docs/sam-migration-freeze.md](../docs/sam-migration-freeze.md).

## Files Kept For Reference

- `app.py`: the custom Lambda application logic for anomaly detection, Jira ticket creation, notifications, and remediation
- `template.yaml`: the custom SAM infrastructure template for the Lambda function and supporting AWS resources
- `samconfig.toml`: the deployment configuration and parameter defaults for the SAM project

## Removal Gate

Delete this folder only after Jenkins completes Terraform apply and smoke tests for the target release. The latest checked pipeline log showed smoke tests were skipped because an earlier stage failed, so the folder remains for comparison.

## Do Not Run

Do not run `sam build` or `sam deploy` from this folder. Doing so would create a second, unmanaged deployment path outside Terraform state.
