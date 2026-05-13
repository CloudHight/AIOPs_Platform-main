resource "aws_secretsmanager_secret" "jira_credentials" {
  #checkov:skip=CKV2_AWS_57: Jira API tokens require provider-side/manual rotation; operational rotation is documented rather than automated by Lambda.
  name                    = coalesce(var.jira_secret_name, "${var.name_prefix}-jira-credentials-${var.environment}")
  description             = "Jira API credentials for the AIOps anomaly detection system"
  kms_key_id              = var.kms_key_arn
  recovery_window_in_days = var.recovery_window_in_days

  tags = var.common_tags
}
