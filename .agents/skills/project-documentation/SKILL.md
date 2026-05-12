---
description: Use when creating senior-level documentation, README updates, architecture explanations, runbooks, or project-defense material for the AIOps platform.
---

# Project Documentation Skill

## Goal
Produce clear senior-level documentation that explains the AIOps platform technically and operationally.

## Use this skill when
- Updating `README.md`.
- Creating architecture documentation.
- Creating deployment guides.
- Creating project defense questions and answers.
- Writing runbooks.
- Explaining the Terraform + Jenkins delivery model.

## Required docs
Maintain these files:

```text
docs/
├── architecture.md
├── deployment.md
├── operations-runbook.md
├── security.md
├── modelops.md
├── cicd.md
└── project-defense.md
```

## README structure
The top-level README should include:

1. Project overview
2. Architecture diagram or text flow
3. Services used
4. Repository layout
5. Prerequisites
6. Jenkins CI/CD overview
7. Terraform deployment overview
8. ModelOps workflow
9. Security considerations
10. Smoke testing
11. Cleanup/destroy instructions
12. Troubleshooting

## Architecture explanation format
Use this flow:

```text
1. Jenkins trains and validates models.
2. Jenkins uploads approved model artifacts to S3.
3. Terraform deploys SageMaker endpoints using approved artifacts.
4. Terraform provisions the monitored EC2 workload.
5. EC2 publishes CPU metrics and Nginx logs to CloudWatch.
6. EventBridge invokes Lambda on a schedule.
7. Lambda discovers tagged EC2 instances.
8. Lambda fetches metrics/logs and invokes SageMaker endpoints.
9. Lambda records anomalies in DynamoDB.
10. Lambda sends SNS alerts and creates Jira tickets.
11. Lambda sends delayed SQS remediation messages.
12. Remediation handler re-checks the anomaly and safely acts if needed.
```

## Project defense content
Create questions and answers around:

- Why Terraform instead of SAM for final delivery?
- Why Jenkins for CI/CD?
- Why not train models inside Terraform?
- How CPU anomaly detection works.
- How log anomaly detection works.
- How Lambda discovers instances.
- How CloudWatch metrics/logs become inference payloads.
- How SQS grace period prevents premature remediation.
- How duplicate Jira tickets are avoided.
- How IAM least privilege is implemented.
- How the system is tested end-to-end.
- How to roll back a bad model or Lambda deployment.
- How to secure credentials and state.

## Runbook format
For each alarm or incident, document:

- Symptom
- Likely causes
- First checks
- AWS CLI commands
- Dashboard/log locations
- Remediation steps
- Escalation criteria
- Rollback/cleanup steps

## Writing style
- Write for a cloud engineer evaluating the project.
- Be specific and technical.
- Avoid vague claims such as "production ready" unless the supporting controls are present.
- Use diagrams or sequence flows where helpful.
- Keep commands copy-pasteable.

## Acceptance criteria
Documentation is complete when:

- A new engineer can deploy dev from scratch.
- A reviewer can understand every AWS service used.
- A project-defense candidate can explain the design choices.
- Operators can troubleshoot common failure modes.
- Security and cleanup steps are explicit.
