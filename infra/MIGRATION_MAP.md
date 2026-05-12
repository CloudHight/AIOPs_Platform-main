# Terraform Migration Map

This map defines where the current learning/demo resources are moving during the Terraform migration.

| Current source | Current resource | Target Terraform module | Notes/Risks |
|---|---|---|---|
| `TERRAFORM_Code/main.tf` | EC2 instance, security group, instance profile | `infra/modules/ec2-workload` | Migrated into module and wired into `infra/envs/dev`; SSM-only access preserved, no SSH/key material. |
| `TERRAFORM_Code/userdata.sh` | Nginx, Docker app, CloudWatch Agent bootstrap | `infra/modules/ec2-workload` | Migrated to `templates/userdata.sh.tftpl`; no embedded registry credentials. |
| `AIOPs_SAM/template.yaml` | Lambda anomaly processor | `infra/modules/lambda-function` | Converted; Jenkins must package and publish the Lambda zip before apply. |
| `AIOPs_SAM/template.yaml` | Lambda IAM policies | `infra/modules/lambda-function` | Converted with scoped policies and tagged remediation targets. Dedicated `iam` module remains available for future extraction. |
| `AIOPs_SAM/template.yaml` | DynamoDB anomaly table | `infra/modules/dynamodb` | Converted with TTL, PITR, GSIs, and optional KMS. |
| `AIOPs_SAM/template.yaml` | SQS remediation queue and DLQ | `infra/modules/sqs` | Converted with redrive policy and optional KMS. |
| `AIOPs_SAM/template.yaml` | SNS topic and email subscription | `infra/modules/sns` | Converted; email confirmation remains an operator step. |
| `AIOPs_SAM/template.yaml` | EventBridge schedule, bus, rule | `infra/modules/eventbridge` | Converted; schedule invokes Lambda and bus routes anomaly events to SNS. |
| `AIOPs_SAM/template.yaml` | SSM runtime parameters | `infra/modules/ssm-parameters` | Converted for remediation feature flags and grace period. |
| `AIOPs_SAM/template.yaml` | Jira credentials secret | `infra/modules/secrets-manager` | Converted as secret shell only; secret values must be populated out of band. |
| `AIOPs_SAM/template.yaml` | CloudWatch dashboard and alarms | `infra/modules/cloudwatch-observability` | Converted for dashboard and DLQ alarm. |
| `AIOPs_SAM/template.yaml` | Optional Managed Grafana | `infra/modules/cloudwatch-observability` | Converted as optional workspace; old custom bootstrap Lambda is not carried forward because its source is not present. |
| `RCF_Model/` scripts | CPU SageMaker endpoint | `infra/modules/sagemaker-endpoint` | ModelOps scripts package/upload artifacts; Terraform deploys endpoint resources from immutable artifact URI. |
| `BERT_Model/` scripts | Nginx/log SageMaker endpoint | `infra/modules/sagemaker-endpoint` | ModelOps scripts package/upload artifacts; Terraform deploys endpoint resources from immutable artifact URI. |
