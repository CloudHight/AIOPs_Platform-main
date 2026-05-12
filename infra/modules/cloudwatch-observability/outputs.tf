output "module_name" {
  description = "Module identifier."
  value       = "cloudwatch-observability"
}

output "dashboard_name" {
  description = "CloudWatch dashboard name."
  value       = aws_cloudwatch_dashboard.aiops.dashboard_name
}

output "dlq_alarm_name" {
  description = "DLQ alarm name."
  value       = aws_cloudwatch_metric_alarm.dlq_messages.alarm_name
}

output "alarm_names" {
  description = "CloudWatch alarm names created by this module."
  value = compact([
    aws_cloudwatch_metric_alarm.lambda_errors.alarm_name,
    aws_cloudwatch_metric_alarm.lambda_throttles.alarm_name,
    aws_cloudwatch_metric_alarm.lambda_duration.alarm_name,
    aws_cloudwatch_metric_alarm.dlq_messages.alarm_name,
    aws_cloudwatch_metric_alarm.processing_queue_age.alarm_name,
    aws_cloudwatch_metric_alarm.dynamodb_throttles.alarm_name,
    try(aws_cloudwatch_metric_alarm.ec2_status_check_failed[0].alarm_name, null),
    try(aws_cloudwatch_metric_alarm.nginx_error_volume[0].alarm_name, null)
  ])
}

output "grafana_workspace_id" {
  description = "AWS Managed Grafana workspace ID, if enabled."
  value       = var.enable_managed_grafana ? aws_grafana_workspace.aiops[0].id : null
}

output "grafana_workspace_url" {
  description = "AWS Managed Grafana workspace URL, if enabled."
  value       = var.enable_managed_grafana ? "https://${aws_grafana_workspace.aiops[0].endpoint}" : null
}
