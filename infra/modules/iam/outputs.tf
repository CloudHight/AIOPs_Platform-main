output "module_name" {
  description = "Module identifier."
  value       = "iam"
}

output "lambda_role_arn" {
  description = "Lambda execution role ARN after migration."
  value       = null
}

output "sagemaker_role_arn" {
  description = "SageMaker execution role ARN after migration."
  value       = null
}

