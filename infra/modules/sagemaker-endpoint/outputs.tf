output "module_name" {
  description = "Module identifier."
  value       = "sagemaker-endpoint"
}

output "endpoint_name" {
  description = "SageMaker endpoint name."
  value       = aws_sagemaker_endpoint.this.name
}

output "endpoint_arn" {
  description = "SageMaker endpoint ARN."
  value       = aws_sagemaker_endpoint.this.arn
}

output "model_name" {
  description = "SageMaker model resource name."
  value       = aws_sagemaker_model.this.name
}

output "endpoint_configuration_name" {
  description = "SageMaker endpoint configuration name."
  value       = aws_sagemaker_endpoint_configuration.this.name
}

output "execution_role_arn" {
  description = "SageMaker execution role ARN."
  value       = local.execution_role_arn
}
