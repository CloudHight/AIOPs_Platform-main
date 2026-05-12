output "module_name" {
  description = "Module identifier."
  value       = "secrets-manager"
}

output "jira_secret_arn" {
  description = "Jira credentials secret ARN."
  value       = aws_secretsmanager_secret.jira_credentials.arn
}

output "jira_secret_name" {
  description = "Jira credentials secret name."
  value       = aws_secretsmanager_secret.jira_credentials.name
}
