locals {
  parameter_path = "/AnomalyDetection/${var.environment}"
}

resource "aws_ssm_parameter" "auto_remediation_enabled" {
  name   = "${local.parameter_path}/AutoRemediationEnabled"
  type   = "SecureString"
  key_id = var.kms_key_arn
  value  = tostring(var.auto_remediation_enabled)

  tags = var.common_tags
}

resource "aws_ssm_parameter" "dry_run" {
  name   = "${local.parameter_path}/DryRun"
  type   = "SecureString"
  key_id = var.kms_key_arn
  value  = tostring(var.dry_run)

  tags = var.common_tags
}

resource "aws_ssm_parameter" "grace_period_minutes" {
  name   = "${local.parameter_path}/GracePeriodMinutes"
  type   = "SecureString"
  key_id = var.kms_key_arn
  value  = tostring(var.grace_period_minutes)

  tags = var.common_tags
}

resource "aws_ssm_parameter" "cpu_threshold" {
  name   = "${local.parameter_path}/CpuThreshold"
  type   = "SecureString"
  key_id = var.kms_key_arn
  value  = tostring(var.cpu_threshold)

  tags = var.common_tags
}

resource "aws_ssm_parameter" "log_threshold" {
  name   = "${local.parameter_path}/LogThreshold"
  type   = "SecureString"
  key_id = var.kms_key_arn
  value  = tostring(var.log_threshold)

  tags = var.common_tags
}

resource "aws_ssm_parameter" "max_remediation_attempts" {
  name   = "${local.parameter_path}/MaxRemediationAttempts"
  type   = "SecureString"
  key_id = var.kms_key_arn
  value  = tostring(var.max_remediation_attempts)

  tags = var.common_tags
}

resource "aws_ssm_parameter" "remediation_cooldown_minutes" {
  name   = "${local.parameter_path}/RemediationCooldownMinutes"
  type   = "SecureString"
  key_id = var.kms_key_arn
  value  = tostring(var.remediation_cooldown_minutes)

  tags = var.common_tags
}
