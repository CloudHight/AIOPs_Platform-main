# `AIOPs_SAM/app.py` Explanation

## Purpose

This file contains the main AWS Lambda implementation for the anomaly-detection and auto-remediation system. It monitors tagged EC2 instances, fetches CPU metrics and nginx logs, invokes SageMaker endpoints for anomaly scoring, stores results in DynamoDB, creates Jira tickets, sends SNS notifications, emits EventBridge events, and schedules or executes remediation actions.

## High-level role

`app.py` is the operational core of the whole SAM application. Most of the business logic lives here.

## Main areas of responsibility

### Configuration and environment setup

The file:

- initializes AWS Lambda Powertools logging, tracing, and metrics
- creates AWS clients for CloudWatch, Logs, SageMaker Runtime, DynamoDB, SNS, SQS, SSM, EventBridge, EC2, and Secrets Manager
- reads required environment variables such as:
- DynamoDB table name
- SNS topic ARN
- processing and DLQ URLs
- event bus name
- CPU and log model endpoint names
- Jira settings
- instance tag filters
- log anomaly thresholds and suppression settings

It also defines `AnomalyConfig`, a small configuration object that merges environment defaults with SSM Parameter Store overrides.

### Error and helper types

The file defines custom exception types:

- `AnomalyDetectionError`
- `JiraIntegrationError`
- `SageMakerError`
- `DynamoDBError`

It also includes normalization and timestamp helpers used for deduplication and signature building.

## Detection workflow

### 1. Discover EC2 instances

`get_instances_to_monitor()` finds running EC2 instances that match the configured monitoring tag key and value.

### 2. Fetch data

- `fetch_cpu_metrics(instance_id)` gets the last 15 minutes of `CPUUtilization` metrics from CloudWatch and normalizes the values into a chronological float list.
- `fetch_nginx_logs(instance_id)` retrieves recent nginx log events from CloudWatch Logs using several fallback strategies:
- direct stream name match
- stream name prefix match
- latest streams in the log group
- unfiltered fetch when filtered searches return nothing

### 3. Invoke SageMaker endpoints

- `invoke_sagemaker_model(...)` sends CPU metric values to the CPU anomaly endpoint in CSV format and extracts the latest Random Cut Forest score.
- `invoke_sagemaker_log_model(...)` sends log lines to the text anomaly endpoint in JSON format, parses the returned predictions, and summarizes them.

For log inference, several helpers support downstream decisions:

- `_extract_log_predictions(...)`
- `_summarize_log_predictions(...)`
- `_build_log_detection_signature(...)`
- `get_recent_log_anomaly_history(...)`

These functions turn raw model responses into:

- per-line scores and labels
- anomaly counts
- average and max anomaly scores
- a normalized signature for deduplication
- repeated-detection and Jira-suppression checks

## Post-detection workflow

### Persisting results

`store_inference_result(...)` writes anomaly records to DynamoDB, adds metadata such as environment and status, and sets a 30-day TTL.

### Jira integration

`get_jira_credentials()` retrieves Jira API credentials from Secrets Manager.

`create_jira_ticket(...)` creates a Jira issue using the Jira Cloud REST API and builds the description in Atlassian Document Format.

### Notifications and eventing

- `send_team_notification(...)` publishes alert emails to SNS.
- `emit_eventbridge_event(...)` publishes anomaly events to the custom EventBridge bus.

### Remediation

- `schedule_auto_remediation(...)` queues delayed remediation messages in SQS.
- `trigger_auto_remediation(...)` executes the actual action:
- reboot EC2 instances for CPU anomalies
- restart nginx or a named container for log anomalies

## CPU and log anomaly processors

### `process_cpu_anomaly(...)`

This function:

- rejects low-CPU false positives when max CPU is below 5%
- compares the score against the configured CPU threshold
- stores the anomaly
- emits an event
- creates a Jira ticket
- sends a notification
- schedules remediation

### `process_log_anomaly(...)`

This function:

- uses anomalous line count rather than a single score as the main gate
- builds a detection signature from top anomalous lines
- checks recent history in DynamoDB to suppress duplicate Jira tickets
- stores the anomaly
- emits an event
- creates Jira only when count and repetition rules justify it
- schedules remediation if Jira succeeds

## Event handling flow

### `process_sqs_message(...)`

Handles delayed remediation messages from SQS. If the scheduled time has arrived, it triggers remediation. Otherwise it extends message visibility.

### `process_instance(...)`

Runs both CPU and log anomaly pipelines for a single instance.

### `lambda_handler(...)`

This is the main Lambda entry point. It supports two invocation modes:

- SQS-triggered execution for delayed remediation actions
- scheduled execution for normal monitoring runs

For scheduled runs it:

1. loads configuration
2. discovers monitored instances
3. processes each instance
4. returns a summary response

## Important implementation details

- The file uses AWS Lambda Powertools decorators for structured logs, traces, and custom metrics.
- CPU anomaly scoring assumes the latest score from the SageMaker RCF endpoint is the most relevant one.
- Log anomaly decisions are count-based and include suppression windows to avoid noisy repeated Jira creation.
- DynamoDB is used as the system of record for anomaly state and remediation lifecycle.
- The file includes a `__main__` block with a local test event, although the code is primarily designed for Lambda execution.

## Risks and mismatches

- The SAM template points Lambda `CodeUri` to `src/` with handler `app.lambda_handler`, but the visible file in this folder is `AIOPs_SAM/app.py`. That suggests either the template or the file layout is out of sync.
- The function is large, with most responsibilities concentrated in one file of about 1,600 lines, which increases maintenance risk.
- Many integrations are hard runtime dependencies: SageMaker endpoints, DynamoDB, SNS, SQS, SSM, Secrets Manager, EventBridge, EC2, CloudWatch, and Jira.
