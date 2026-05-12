output "module_name" {
  description = "Module identifier."
  value       = "dynamodb"
}

output "table_name" {
  description = "Anomaly table name."
  value       = aws_dynamodb_table.anomaly_results.name
}

output "table_arn" {
  description = "Anomaly table ARN."
  value       = aws_dynamodb_table.anomaly_results.arn
}
