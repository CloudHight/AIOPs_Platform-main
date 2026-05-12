# `AIOPs_SAM/template.yaml` Explanation

## Purpose

This file is the AWS SAM and CloudFormation template for the anomaly-detection system. It defines the Lambda function, its permissions, supporting AWS resources, monitoring resources, optional Managed Grafana resources, and stack outputs.

## High-level role

`template.yaml` is the infrastructure definition for the whole serverless system. Deploying it creates the AWS resources that `app.py` depends on.

## Major sections

### Globals

The `Globals` section sets shared defaults for Lambda functions:

- timeout `900`
- memory `1024`
- runtime `python3.12`
- tracing enabled
- environment variables for Powertools and deployment environment

### Parameters

The template exposes deployment-time parameters for:

- environment name
- CPU and log anomaly score thresholds
- grace period
- notification email
- SageMaker endpoint names
- Jira project key
- monitoring frequency
- EC2 tag filters
- Managed Grafana enablement and workspace naming

These parameters drive both infrastructure settings and Lambda environment variables.

## Core resources

### `JiraCredentialsSecret`

Creates a Secrets Manager secret to hold Jira API credentials.

### `AnomalyDetectionLambda`

Defines the main Lambda function. Important properties include:

- handler `app.lambda_handler`
- scheduled trigger for periodic monitoring
- SQS trigger for delayed remediation actions
- environment variables that map template parameters and resource references into the runtime
- a broad set of IAM permissions for:
- CloudWatch
- SageMaker endpoint invocation
- Secrets Manager
- DynamoDB
- SNS
- SSM
- SQS
- EventBridge
- EC2
- CloudWatch Logs

### `AnomalyEventBus` and `AnomalyEventRule`

Create a custom EventBridge bus and a rule that forwards certain anomaly events to SNS.

### `AnomalyResultsTable`

Defines the DynamoDB table used to store anomaly records. It includes:

- primary key on `anomaly_id`
- GSIs for instance, model type, and status
- TTL
- point-in-time recovery
- encryption at rest

### `AnomalyNotificationTopic`

Creates an SNS topic with an email subscription for team notifications.

### `AnomalyProcessingQueue` and `AnomalyProcessingDLQ`

Create the main SQS queue for delayed remediation processing and its dead-letter queue.

### `DLQAlarm`

Creates a CloudWatch alarm that alerts when messages land in the dead-letter queue.

### `AutoRemediationParameter` and `GracePeriodParameter`

Create SSM Parameters used by the Lambda configuration lookup logic.

### `AnomalyDashboard`

Creates a CloudWatch dashboard with Lambda, SQS, and DynamoDB metrics.

## Optional Managed Grafana section

If `EnableManagedGrafana` is set to `"true"`, the template also creates:

- `GrafanaWorkspace`
- `GrafanaWorkspaceRole`
- `GrafanaBootstrapFunction`
- `GrafanaBootstrapCustomResource`

This part provisions an AWS Managed Grafana workspace and attempts to bootstrap a dashboard.

## Outputs

The template exports key identifiers such as:

- Lambda ARN and name
- EventBridge bus ARN
- DynamoDB table name
- SNS topic ARN
- queue URLs
- Jira secret ARN
- dashboard name
- optional Grafana workspace and dashboard URLs

## Important mismatches and caveats

- `AnomalyDetectionLambda` uses `CodeUri: src/`, but the visible main code file in this directory is `app.py` at the project root. Unless there is an unseen `src/app.py`, deployment from the current layout would not package the expected handler.
- `GrafanaBootstrapFunction` points to `grafana_provisioner/`, which is not present in the visible `AIOPs_SAM` directory contents.
- The event rule matches source `anomaly-detection-${Environment}`, while the Lambda code emits source strings in the form `anomaly-detection.{ENVIRONMENT}`. That source-format mismatch may prevent the rule from matching events as intended.
- The default CPU threshold in the template is `0.85`, while the Lambda code’s fallback config default is `0.50`. In practice the environment variable should win, but the difference is important to know.

## Why it matters

This template is the deployment backbone of the application. Any mismatch between it and the actual file layout or runtime behavior will directly affect whether the stack can be deployed and whether events, permissions, and integrations work correctly.
