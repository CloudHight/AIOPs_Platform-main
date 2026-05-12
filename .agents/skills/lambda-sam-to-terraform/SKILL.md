---
description: Use when refactoring the AIOPs Lambda from the SAM app, migrating SAM infrastructure to Terraform, or improving Python orchestration logic.
---

# Lambda SAM-to-Terraform Migration Skill

## Goal
Migrate the current SAM-based AIOps control plane into Terraform and refactor the Lambda into maintainable, testable Python modules.

## Use this skill when
- Editing `AIOPs_SAM/app.py`.
- Migrating `AIOPs_SAM/template.yaml` resources into Terraform.
- Creating the target `lambda/src/aiops/` package.
- Packaging Lambda through Jenkins.
- Writing tests for anomaly detection orchestration.

## Required migration steps
1. Read `AIOPs_SAM/app.py` and identify functions by responsibility.
2. Read `AIOPs_SAM/template.yaml` and list all resources, parameters, policies, and event triggers.
3. Create a refactor plan before editing.
4. Move logic into modules, preserving behavior first.
5. Add tests around existing behavior.
6. Replace SAM resource definitions with Terraform modules.
7. Package Lambda with Jenkins.

## Target Python modules
Use this package structure:

```text
lambda/src/aiops/
├── __init__.py
├── handler.py              # Lambda entry points only
├── config.py               # env vars + SSM config loading/cache
├── aws_clients.py          # boto3 client/session factory
├── discovery.py            # EC2 instance discovery by tag
├── metrics_reader.py       # CloudWatch CPU metric fetch
├── logs_reader.py          # CloudWatch Logs fetch/filter
├── inference.py            # SageMaker invocation and response parsing
├── anomaly_store.py        # DynamoDB writes/dedup/TTL/status
├── alerting.py             # SNS notification logic
├── jira_client.py          # Jira ticket create/search/update
├── remediation.py          # SQS scheduling, EC2 reboot, SSM commands
├── events.py               # EventBridge event emission
├── models.py               # dataclasses/types
└── errors.py               # custom exceptions
```

## Handler rules
- `handler.py` should be thin.
- It may route scheduled detection events and SQS remediation events.
- It should not contain large business logic.
- It should return structured status for tests and manual invocations.

## Configuration rules
- Required config comes from environment variables.
- Runtime-tunable config comes from SSM Parameter Store.
- Secrets come from Secrets Manager.
- Cache SSM/secret reads within the Lambda execution context.
- Fail fast when required config is missing.

## Logging rules
Use structured JSON logs with fields such as:

- `event_type`
- `instance_id`
- `anomaly_type`
- `correlation_id`
- `severity`
- `sagemaker_endpoint`
- `jira_issue_key`
- `remediation_action`
- `status`
- `error_type`

Do not log secrets, Jira API tokens, full authorization headers, or sensitive payloads.

## Idempotency rules
Implement idempotency for:

- anomaly records
- SNS alert sends
- Jira ticket creation
- remediation scheduling
- remediation execution

Recommended DynamoDB keys:

- partition key: `PK = INSTANCE#<instance-id>` or `ANOMALY#<hash>`
- sort key: `SK = <timestamp-or-anomaly-type>`
- optional GSI for open anomalies by instance/type

## Lambda packaging rules
Jenkins should:

1. Install dependencies into a build directory.
2. Copy `lambda/src` into the build directory.
3. Zip deterministically.
4. Produce `dist/aiops-lambda.zip` and `dist/aiops-lambda.zip.sha256`.
5. Upload artifact to S3 or pass it to Terraform.

Terraform should set `source_code_hash` to force safe Lambda updates.

## Test requirements
Write tests for:

- config loading and defaults
- EC2 discovery filtering
- CPU metric ordering and missing datapoints
- log filtering rules
- SageMaker payload formatting
- SageMaker response parsing
- anomaly dedupe behavior
- Jira duplicate prevention
- SQS remediation message format
- remediation safety guards

## Acceptance criteria
The migration is complete when:

- SAM is no longer needed for deployment.
- Lambda can be packaged by Jenkins.
- Terraform deploys the Lambda and all event sources.
- Unit tests cover critical logic.
- Smoke tests invoke the deployed function successfully.
- The code is understandable to a senior DevOps/cloud engineer during project defense.
