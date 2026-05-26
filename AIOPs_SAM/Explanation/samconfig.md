# `AIOPs_SAM/samconfig.toml` Explanation

> Legacy reference only: do not use this SAM configuration for deployment. The active deployment path is Jenkins plus Terraform under `infra/`.

## Purpose

This file stores default AWS SAM CLI configuration for building, validating, packaging, syncing, local development, and especially deployment.

## What it configures

### Deployment defaults

Under `[default.deploy.parameters]`, it sets:

- stack name: `anomaly-detection-stack`
- auto-managed S3 packaging
- region: `us-east-1`
- confirmation before applying changesets
- capabilities: `CAPABILITY_IAM CAPABILITY_AUTO_EXPAND`
- rollback disabled

It also defines a long `parameter_overrides` string that pre-populates stack parameters such as:

- environment
- CPU and log thresholds
- grace period
- notification email
- SageMaker endpoint names
- Jira project key
- monitoring frequency
- instance tag filters
- Managed Grafana settings

### Build defaults

The build section enables:

- caching
- parallel builds

### Sync and validate

It enables:

- watch mode for `sam sync`
- linting for `sam validate`

### Local development

It sets eager warm containers for:

- `sam local start-api`
- `sam local start-lambda`

## Why it matters

This file captures the deployment assumptions for the project. It allows `sam deploy` and related commands to run without re-entering the same values each time.

## Important observations

- The configured CPU threshold is `1.4059`, which is notably higher than the code-level default and template default. That means actual deployed behavior will likely be stricter than the fallback values in code.
- `disable_rollback = true` is useful for debugging failed deployments but can leave partially created resources in place.
- The file contains a real-looking notification email and project-specific parameter values, so it behaves like an environment-specific config rather than a generic sample.

## Relationship to the other files

- It feeds parameter values into `template.yaml`.
- Those template parameters are then passed as Lambda environment variables consumed by `app.py`.
- It effectively bridges local SAM CLI usage and the deployed anomaly-detection system.
