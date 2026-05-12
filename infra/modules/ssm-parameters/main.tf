locals {
  parameter_path = "/AnomalyDetection/${var.environment}"
}

resource "aws_ssm_parameter" "auto_remediation_enabled" {
  name  = "${local.parameter_path}/AutoRemediationEnabled"
  type  = "String"
  value = tostring(var.auto_remediation_enabled)

  tags = var.common_tags
}

resource "aws_ssm_parameter" "dry_run" {
  name  = "${local.parameter_path}/DryRun"
  type  = "String"
  value = tostring(var.dry_run)

  tags = var.common_tags
}

resource "aws_ssm_parameter" "grace_period_minutes" {
  name  = "${local.parameter_path}/GracePeriodMinutes"
  type  = "String"
  value = tostring(var.grace_period_minutes)

  tags = var.common_tags
}

resource "aws_ssm_parameter" "cpu_threshold" {
  name  = "${local.parameter_path}/CpuThreshold"
  type  = "String"
  value = tostring(var.cpu_threshold)

  tags = var.common_tags
}

resource "aws_ssm_parameter" "log_threshold" {
  name  = "${local.parameter_path}/LogThreshold"
  type  = "String"
  value = tostring(var.log_threshold)

  tags = var.common_tags
}

resource "aws_ssm_parameter" "max_remediation_attempts" {
  name  = "${local.parameter_path}/MaxRemediationAttempts"
  type  = "String"
  value = tostring(var.max_remediation_attempts)

  tags = var.common_tags
}

resource "aws_ssm_parameter" "remediation_cooldown_minutes" {
  name  = "${local.parameter_path}/RemediationCooldownMinutes"
  type  = "String"
  value = tostring(var.remediation_cooldown_minutes)

  tags = var.common_tags
}
