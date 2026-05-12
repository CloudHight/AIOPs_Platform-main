# Security Findings

Review date: 2026-05-09

Scope reviewed:

- `TERRAFORM_Code/main.tf`
- `TERRAFORM_Code/userdata.sh`
- `AIOPs_SAM/template.yaml`
- `AIOPs_SAM/app.py`
- `AIOPs_SAM/samconfig.toml`
- repository scaffolding, `.gitignore`, and documentation placeholders

This is a source review only. No AWS account, deployed resources, Terraform state, Jenkins controller, or Git history were inspected from this workspace.

## Executive Summary

The repo is still in a demo/learning security posture. The highest-risk issues are an exposed Docker credential, public SSH exposure, locally generated private key material, broad Lambda IAM permissions, and unsafe default auto-remediation behavior. Treat the Docker credential as compromised and rotate it before any further deployment.

## Findings

### CRITICAL: Hardcoded Docker Registry Credential

Status: Remediated in source; external credential rotation still required.

Evidence:

- Original finding: `TERRAFORM_Code/userdata.sh` logged in with `docker login -u cloudhight -p ...`.
- Current source no longer contains the Docker login command or embedded password.

Risk:

- The password is committed in source and would also be exposed through EC2 user data, shell history/process lists during bootstrap, and any copied deployment artifact.
- Anyone with repo access can attempt to use the credential.

Remediation:

- Rotate the credential immediately.
- Remove Docker Hub password authentication from user data.
- Prefer ECR with instance-profile IAM permissions.
- If a private external registry must be used temporarily, retrieve a short-lived token from Secrets Manager or SSM SecureString at boot and avoid printing it.

### HIGH: Public SSH Ingress

Status: Remediated in source.

Evidence:

- Original finding: `TERRAFORM_Code/main.tf` allowed TCP/22 from `0.0.0.0/0`.
- Current source no longer creates an SSH ingress rule.

Risk:

- The workload host is directly reachable for SSH from the internet.
- This conflicts with the project requirement to prefer SSM Session Manager and disallow public SSH.

Remediation:

- Remove the SSH ingress rule.
- Remove EC2 key-pair usage.
- Use `AmazonSSMManagedInstanceCore` and SSM Session Manager for access.
- If interactive access is unavoidable in a demo, restrict ingress to a controlled CIDR and document the temporary exception.

### HIGH: Terraform Generates and Writes Private Key Material Locally

Status: Remediated in source.

Evidence:

- Original finding: `TERRAFORM_Code/main.tf` created `tls_private_key`, wrote `ai-app-key.pem` with `local_file`, and registered an EC2 key pair.
- Current source no longer creates Terraform-managed private keys or EC2 key pairs.

Risk:

- Private keys can leak through local workstations, backups, logs, or state files.
- The private key will also be stored in Terraform state.

Remediation:

- Remove `tls_private_key`, `local_file`, `aws_key_pair`, and `key_name`.
- Use SSM Session Manager.
- Rotate/destroy any EC2 key pair previously created by this configuration.

### HIGH: Broad Lambda IAM Permissions

Status: Partially remediated in source.

Evidence:

- `AIOPs_SAM/template.yaml:171-182` grants SSM parameter and command actions on `Resource: "*"`.
- `AIOPs_SAM/template.yaml:196-202` grants EventBridge `events:PutEvents` on `Resource: "*"`.
- `AIOPs_SAM/template.yaml:203-211` grants EC2 describe and reboot permissions on `Resource: "*"`.
- `AIOPs_SAM/template.yaml:212-220` grants CloudWatch Logs reads on `Resource: "*"`.
- `AIOPs_SAM/template.yaml:550-559` grants Grafana API key actions on `Resource: "*"`.

Applied source changes:

- Replaced Lambda `CloudWatchReadOnlyAccess` with explicit CloudWatch metric read actions.
- Scoped EventBridge `PutEvents` to the anomaly event bus.
- Scoped SSM parameter reads to `/AnomalyDetection/${Environment}/*`.
- Scoped SSM send-command instance access to tagged EC2 instances.
- Scoped EC2 reboot to tagged EC2 instances.
- Scoped Nginx log event reads to `nginx/*` log groups.

Residual risk:

- Some read/list actions still require `Resource: "*"` in AWS IAM.
- The optional Grafana bootstrap policy still has wildcard workspace API-key permissions and should be revisited during the Terraform migration.

Risk:

- A compromised Lambda role could query wider account state, send SSM commands broadly, write arbitrary events, or reboot unapproved instances.
- Wildcard permissions make automated remediation more dangerous.

Remediation:

- Scope permissions to exact ARNs for SSM parameter paths, EventBridge bus, log groups, queues, topics, tables, secrets, and SageMaker endpoints.
- Restrict EC2 remediation actions to instances tagged `Project=AIOps` and `AnomalyMonitoring=enabled` where IAM condition support allows.
- Split permissions into separate execution roles for anomaly detection, remediation, and Grafana bootstrap if behavior remains separate.

### HIGH: Auto-Remediation Enabled by Default

Status: Remediated in source.

Evidence:

- Original finding: Lambda defaults enabled remediation and non-dry-run mode.
- Current source defaults `AUTO_REMEDIATION_ENABLED` to `false` and `DRY_RUN` to `true`.
- SAM parameters now default `AutoRemediationEnabled` to `false` and `DryRun` to `true`.

Risk:

- False positives or model/config errors can trigger disruptive production actions.
- Default behavior is action-oriented rather than safe-by-default.

Remediation:

- Default `AutoRemediationEnabled` to `false`.
- Add an explicit `DryRun` SSM parameter defaulting to `true`.
- Require environment-specific approval before enabling remediation, especially in `stage` and `prod`.
- Enforce attempt limits, cooldowns, and re-checks before every action.

### HIGH: Remediation Does Not Re-Validate Resource Eligibility Before Acting

Status: Partially remediated in source.

Evidence:

- `AIOPs_SAM/app.py:988-1024` executes reboot/restart based on SQS message anomaly data.
- `AIOPs_SAM/app.py:1378-1399` processes delayed SQS messages and calls remediation once `execute_at` has passed.

Applied source changes:

- Remediation now reloads the DynamoDB anomaly record before acting.
- Remediation skips terminal statuses and enforces a configurable attempt limit.
- Remediation validates that the target EC2 instance is running and tagged with both `AnomalyMonitoring=enabled` and `Project=AIOPs`.
- Ineligible remediation attempts are recorded as `remediation_skipped`.

Residual risk:

- The code still does not perform a fresh CloudWatch/SageMaker anomaly re-check immediately before remediation. That should be added during the Lambda module refactor.

Risk:

- If a queue message is stale, malformed, replayed, or created before a tag change, remediation may act on an instance that is no longer eligible.
- There is no visible pre-action check for current instance tags, current anomaly state, attempt count, or cooldown in `trigger_auto_remediation`.

Remediation:

- Reload the anomaly record from DynamoDB before remediation.
- Re-check CloudWatch metrics/logs and SageMaker inference.
- Confirm the instance still has `AnomalyMonitoring=enabled` and project tags.
- Enforce maximum attempts per anomaly and per instance.
- Treat unknown or stale messages as skipped, not actionable.

### MEDIUM: Jira Payload and Error Logging Can Leak Sensitive Operational Data

Evidence:

- `AIOPs_SAM/app.py:777-778` logs the Jira REST URL and full issue payload at debug level.
- `AIOPs_SAM/app.py:799-804` logs up to 1,000 characters of Jira response body on failure.
- `AIOPs_SAM/app.py:1471` injects Lambda context with `log_event=True`.
- `AIOPs_SAM/app.py:1478` logs the event again at debug level.

Risk:

- Logs may contain instance IDs, sampled evidence, operational metadata, Jira error details, or SQS message bodies.
- If event payloads ever include secrets or credentials by mistake, they will be written to CloudWatch Logs.

Remediation:

- Set `log_event=False`.
- Remove full payload logging or redact evidence fields.
- Do not log Jira response bodies except sanitized status/error codes.
- Add a logging policy that redacts credentials, headers, tokens, request bodies, and anomaly evidence where needed.

### MEDIUM: Secret Placeholder Workflow Encourages Manual Template Edits

Evidence:

- `AIOPs_SAM/template.yaml:112-115` includes Jira placeholder values in `SecretStringTemplate`.
- `AIOPs_SAM/README.md:109-114` instructs users to review and update Jira credential placeholders in `template.yaml`.

Risk:

- Users may put real Jira credentials directly into versioned infrastructure templates.
- This conflicts with the repo requirement to never commit Jira tokens.

Remediation:

- Do not ask users to edit secret values into templates.
- Create the Secrets Manager secret shell in Terraform/SAM without secret values, or accept an existing secret ARN.
- Populate secrets out-of-band through AWS CLI, console, or Jenkins credentials binding.

### MEDIUM: Default VPC and Public Workload Exposure

Evidence:

- `TERRAFORM_Code/main.tf:67-75` deploys into the default VPC.
- `TERRAFORM_Code/main.tf:50-56` allows HTTP from `0.0.0.0/0`.
- `TERRAFORM_Code/main.tf:86` enables a public IP.

Risk:

- The application is internet-facing without ALB/WAF, TLS, access restrictions, or documented demo-only controls.
- Default VPC networking is hard to review and reproduce across environments.

Remediation:

- Create explicit networking modules.
- For production, place workload behind ALB/WAF with TLS.
- If direct HTTP is retained for demo, make allowed CIDRs configurable and document the exception.

### MEDIUM: AWS Managed KMS Keys Used Instead of Project CMKs

Evidence:

- `AIOPs_SAM/template.yaml:366` uses `alias/aws/sns`.
- `AIOPs_SAM/template.yaml:386` and `399` use `alias/aws/sqs`.
- `AIOPs_SAM/template.yaml:308-309` enables DynamoDB SSE but does not specify a customer-managed key.
- `AIOPs_SAM/template.yaml:107-115` creates a secret without an explicit customer-managed KMS key.

Risk:

- AWS managed keys are acceptable for some demos, but they do not meet the project’s stated target of KMS keys for logs, DynamoDB, SQS, SNS, Secrets Manager, and state where possible.
- Key policies, rotation, access separation, and auditability are weaker than a project CMK design.

Remediation:

- Add a KMS module with environment-specific customer-managed keys.
- Use CMKs for DynamoDB, SQS, SNS, Secrets Manager, CloudWatch Logs where required, model artifacts, and Terraform state.

### MEDIUM: No Explicit CloudWatch Log Retention or Log Encryption

Evidence:

- `AIOPs_SAM/template.yaml` defines Lambda functions and dashboards, but no explicit `AWS::Logs::LogGroup` resources for Lambda retention/encryption.
- `TERRAFORM_Code/userdata.sh:74-91` configures Nginx log shipping but does not create log groups with retention or KMS.

Risk:

- Logs can be retained indefinitely by default.
- Operational evidence may include IPs, request paths, instance IDs, and failure details.

Remediation:

- Create all application and Lambda log groups explicitly in Terraform.
- Set retention per environment.
- Add KMS encryption if required by the platform security target.

### MEDIUM: SAM Deployment Has Rollback Disabled

Evidence:

- `AIOPs_SAM/samconfig.toml:12` sets `disable_rollback = true`.

Risk:

- Failed deployments may leave partially created IAM, Lambda, queue, dashboard, or secret resources.
- Partial resources can increase attack surface and complicate cleanup.

Remediation:

- Re-enable rollback for normal deployments.
- Use change sets and Terraform saved plans in the target pipeline.
- Keep failed-deployment diagnostics in CI artifacts rather than leaving stacks half-created.

### MEDIUM: Missing CI Security Gates

Evidence:

- `Jenkinsfile` is currently a placeholder.
- A repo scan only found security gate requirements in documentation, not executable checks.

Risk:

- Secret scanning, IaC scanning, Terraform linting, and dependency scanning are not enforced.
- Regressions can enter the repo unnoticed.

Remediation:

- Add Jenkins stages for `gitleaks` or equivalent, `tflint`, `checkov` or `tfsec`, `bandit`, and `pip-audit` where practical.
- Fail builds on high/critical issues unless a reviewed exception is committed.

### LOW: `.gitignore` Does Not Cover All Generated/Sensitive Build Artifacts

Evidence:

- `.gitignore:1-42` covers Terraform state, `.tfvars`, `.pem`, and macOS files.
- It does not currently cover Python caches, virtualenvs, Lambda build zips, `.aws-sam/`, reports, or model output artifacts.

Risk:

- Generated packages, local dependencies, reports, or model artifacts may be accidentally committed.

Remediation:

- Add ignores for `.venv/`, `__pycache__/`, `.pytest_cache/`, `dist/`, `build/`, `.aws-sam/`, `reports/`, `*.zip`, generated model data/artifacts, and local SageMaker output files.

## Recommended Remediation Order

1. Rotate the exposed Docker credential and remove registry login from user data.
2. Remove public SSH and local private-key generation; use SSM Session Manager.
3. Make auto-remediation disabled/dry-run by default.
4. Scope Lambda IAM permissions and add tag-based remediation guardrails.
5. Remove sensitive payload/event logging.
6. Stop editing secrets into templates; use existing secret ARNs or out-of-band secret population.
7. Add explicit log groups, retention, encryption, and KMS CMKs.
8. Add Jenkins security gates.
9. Expand `.gitignore` for generated artifacts.

## Notes for Terraform Migration

When migrating from SAM and `TERRAFORM_Code/` into `infra/`, preserve these security constraints from the start:

- No public SSH.
- No generated private keys in Terraform state.
- No hardcoded Docker/Jira credentials.
- Separate IAM roles for Jenkins, EC2, Lambda, and SageMaker.
- Project tags on every resource: `Project=AIOps`, `Environment`, `ManagedBy=Terraform`.
- Remediation permissions constrained to tagged resources.
- KMS encryption for state, artifacts, DynamoDB, SQS, SNS, Secrets Manager, and log groups where required.
- Security scans must run before Terraform plan/apply.
