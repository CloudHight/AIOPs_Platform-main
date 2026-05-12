# Operational Validation

Use this checklist after Jenkins applies an environment.

## Automated Checks

```bash
scripts/smoke_test.sh <environment>
```

The script must pass before promotion. It validates:

- Terraform outputs
- monitored EC2 discovery tags
- CloudWatch CPU metrics
- Nginx log groups
- SageMaker endpoint invocation when endpoints are managed
- Lambda invocation when the control plane is enabled
- DynamoDB, SQS, EventBridge, CloudWatch dashboard, and alarms

## Synthetic Checks

Run only in dev or approved stage windows:

```bash
ALLOW_SYNTHETIC_ANOMALY_TEST=true scripts/smoke_test.sh dev
```

Confirm after the next scheduled detection run:

- DynamoDB anomaly record exists
- EventBridge emitted anomaly lifecycle events
- SNS notification was sent
- Jira ticket was created or Jira failure was recorded
- SQS grace-period message was scheduled
- remediation was skipped while `DryRun=true`

## Manual Dashboard Review

Open the dashboard from:

```bash
terraform -chdir=infra/envs/<environment> output aiops_cloudwatch_dashboard_name
```

Check Lambda, queue, DynamoDB, workload, SageMaker, and incident-flow panels.

## Promotion Gate

Do not promote to `stage` or `prod` unless:

- smoke report status is `passed`
- no critical alarms are in `ALARM`
- Lambda package hash is archived by Jenkins
- Terraform plan is archived by Jenkins
- model metadata and evaluation files are archived by Jenkins
