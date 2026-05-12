---
description: Use when implementing or reviewing anomaly lifecycle, Jira incident creation, alerting, SQS grace period, and automated remediation behavior.
---

# Incident and Remediation Skill

## Goal
Make anomaly response safe, idempotent, auditable, and suitable for production operations.

## Use this skill when
- Editing alerting, Jira, DynamoDB, SQS, or remediation logic.
- Designing the anomaly lifecycle.
- Adding grace-period behavior.
- Preventing duplicate alerts or tickets.
- Reviewing automated EC2 reboot or Nginx/container restart logic.

## Anomaly lifecycle
Use a clear lifecycle:

```text
DETECTED -> RECORDED -> ALERTED -> TICKETED -> GRACE_PERIOD -> RECHECKED -> REMEDIATED -> VERIFIED -> CLOSED
```

Also support failure states:

```text
REMEDIATION_SKIPPED
REMEDIATION_FAILED
JIRA_FAILED
ALERT_FAILED
FALSE_POSITIVE
```

## DynamoDB design expectations
The anomaly table should support:

- finding open anomaly by instance and type
- deduplicating repeated detections
- storing TTL for old records
- tracking Jira issue key
- tracking remediation attempts
- storing last score/severity
- storing timestamps for detection, alert, ticket, scheduled remediation, execution, and resolution

## Idempotency requirements
Do not create duplicate Jira tickets or repeated remediation loops.

Before creating a ticket:
- check for existing open anomaly record
- check stored Jira issue key
- optionally search Jira by external correlation ID

Before remediation:
- re-check if anomaly still exists
- check attempt count
- check cooldown window
- check remediation feature flag
- check environment policy

## SQS grace-period pattern
Detection Lambda should:

1. detect anomaly
2. persist anomaly record
3. send alert
4. create/update Jira ticket
5. send SQS message with delay/grace period

SQS remediation handler should:

1. receive delayed message
2. reload anomaly record
3. re-check CloudWatch metrics/logs and/or SageMaker inference
4. skip if recovered
5. execute safe remediation if still anomalous
6. record status and emit EventBridge event

## CPU remediation
For CPU anomalies:

- Preferred safe action in demo: reboot EC2 only when explicitly enabled.
- Production alternative: scale out, restart service, or notify human depending on architecture.
- Always check instance tag before reboot.
- Record reason and correlation ID.
- Limit repeated reboot attempts.

## Log/Nginx remediation
For log anomalies:

- Use SSM to run a controlled document/command.
- Restart Nginx and the application container only through approved commands.
- Do not execute arbitrary command text from events or external inputs.
- Capture command ID and result.
- Record failure output safely without secrets.

## Jira incident requirements
Jira ticket should include:

- anomaly type
- instance ID
- environment
- severity
- model endpoint name
- anomaly score/confidence
- sampled evidence
- detection timestamp
- remediation status
- correlation ID
- runbook link

Use a deterministic external correlation ID in the summary/body to prevent duplicate tickets.

## EventBridge events
Emit events for:

- anomaly detected
- alert sent
- Jira ticket created/updated
- remediation scheduled
- remediation skipped
- remediation succeeded
- remediation failed

Each event should include `correlation_id`, `environment`, `instance_id`, and `anomaly_type`.

## Acceptance criteria
Incident/remediation logic is complete when:

- Duplicate anomalies do not create duplicate Jira tickets.
- SQS delay implements a real grace period.
- Remediation re-checks before acting.
- Remediation is gated by config and environment.
- Every action is recorded in DynamoDB and EventBridge.
- Smoke tests can validate the flow without causing unsafe actions.
