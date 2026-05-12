output "module_name" {
  description = "Module identifier."
  value       = "aiops-control-plane"
}

output "lambda_function_name" {
  description = "AIOps Lambda function name."
  value       = module.lambda_function.function_name
}

output "lambda_function_arn" {
  description = "AIOps Lambda function ARN."
  value       = module.lambda_function.function_arn
}

output "event_bus_name" {
  description = "AIOps EventBridge bus name."
  value       = module.eventbridge.event_bus_name
}

output "event_bus_arn" {
  description = "AIOps EventBridge bus ARN."
  value       = module.eventbridge.event_bus_arn
}

output "dynamodb_table_name" {
  description = "Anomaly table name."
  value       = module.dynamodb.table_name
}

output "sns_topic_arn" {
  description = "SNS notification topic ARN."
  value       = module.sns.topic_arn
}

output "sqs_processing_queue_url" {
  description = "SQS processing queue URL."
  value       = module.sqs.queue_url
}

output "sqs_dead_letter_queue_url" {
  description = "SQS dead-letter queue URL."
  value       = module.sqs.dlq_url
}

output "jira_credentials_secret_arn" {
  description = "Jira credentials secret ARN."
  value       = module.secrets_manager.jira_secret_arn
}

output "cloudwatch_dashboard_name" {
  description = "CloudWatch dashboard name."
  value       = module.cloudwatch_observability.dashboard_name
}

output "cloudwatch_alarm_names" {
  description = "CloudWatch alarm names for platform health."
  value       = module.cloudwatch_observability.alarm_names
}

output "grafana_workspace_id" {
  description = "AWS Managed Grafana workspace ID, if enabled."
  value       = module.cloudwatch_observability.grafana_workspace_id
}

output "grafana_workspace_url" {
  description = "AWS Managed Grafana workspace URL, if enabled."
  value       = module.cloudwatch_observability.grafana_workspace_url
}
