output "module_name" {
  description = "Module identifier."
  value       = "lambda-function"
}

output "function_name" {
  description = "Lambda function name."
  value       = aws_lambda_function.anomaly_detection.function_name
}

output "function_arn" {
  description = "Lambda function ARN."
  value       = aws_lambda_function.anomaly_detection.arn
}

output "role_arn" {
  description = "Lambda execution role ARN."
  value       = aws_iam_role.lambda.arn
}

output "log_group_name" {
  description = "Lambda log group name."
  value       = aws_cloudwatch_log_group.lambda.name
}
