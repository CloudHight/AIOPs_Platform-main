output "module_name" {
  description = "Module identifier."
  value       = "ssm-parameters"
}

output "parameter_path" {
  description = "SSM parameter path."
  value       = local.parameter_path
}

output "parameter_arns" {
  description = "Runtime parameter ARNs."
  value = {
    auto_remediation_enabled     = aws_ssm_parameter.auto_remediation_enabled.arn
    dry_run                      = aws_ssm_parameter.dry_run.arn
    grace_period_minutes         = aws_ssm_parameter.grace_period_minutes.arn
    cpu_threshold                = aws_ssm_parameter.cpu_threshold.arn
    log_threshold                = aws_ssm_parameter.log_threshold.arn
    max_remediation_attempts     = aws_ssm_parameter.max_remediation_attempts.arn
    remediation_cooldown_minutes = aws_ssm_parameter.remediation_cooldown_minutes.arn
  }
}
