output "environment" {
  description = "Environment represented by this root module."
  value       = var.environment
}

output "common_tags" {
  description = "Common tags applied by the AWS provider."
  value       = local.common_tags
}

output "workload_instance_id" {
  description = "Monitored workload instance ID."
  value       = module.ec2_workload.instance_id
}

output "workload_instance_public_ip" {
  description = "Monitored workload public IP, if associated."
  value       = module.ec2_workload.instance_public_ip
}

output "workload_public_url" {
  description = "Temporary stage/demo HTTP URL for direct access to the workload instance public IP."
  value       = module.ec2_workload.instance_public_url
}

output "workload_security_group_id" {
  description = "Security group ID for the monitored workload."
  value       = module.ec2_workload.security_group_id
}

output "workload_nginx_access_log_group_name" {
  description = "Nginx access log group name."
  value       = module.ec2_workload.nginx_access_log_group_name
}

output "workload_nginx_error_log_group_name" {
  description = "Nginx error log group name."
  value       = module.ec2_workload.nginx_error_log_group_name
}

output "aiops_lambda_function_name" {
  description = "AIOps Lambda function name when control plane is enabled."
  value       = try(module.aiops_control_plane[0].lambda_function_name, null)
}

output "aiops_event_bus_name" {
  description = "AIOps EventBridge bus name when control plane is enabled."
  value       = try(module.aiops_control_plane[0].event_bus_name, null)
}

output "aiops_dynamodb_table_name" {
  description = "AIOps anomaly table name when control plane is enabled."
  value       = try(module.aiops_control_plane[0].dynamodb_table_name, null)
}

output "aiops_sqs_processing_queue_url" {
  description = "AIOps SQS processing queue URL when control plane is enabled."
  value       = try(module.aiops_control_plane[0].sqs_processing_queue_url, null)
}

output "aiops_cloudwatch_dashboard_name" {
  description = "AIOps CloudWatch dashboard name when control plane is enabled."
  value       = try(module.aiops_control_plane[0].cloudwatch_dashboard_name, null)
}

output "aiops_cloudwatch_alarm_names" {
  description = "AIOps CloudWatch alarm names when control plane is enabled."
  value       = try(module.aiops_control_plane[0].cloudwatch_alarm_names, [])
}

output "cpu_sagemaker_endpoint_name" {
  description = "CPU SageMaker endpoint name when managed by Terraform."
  value       = try(module.cpu_sagemaker_endpoint[0].endpoint_name, null)
}

output "log_sagemaker_endpoint_name" {
  description = "Log SageMaker endpoint name when managed by Terraform."
  value       = try(module.log_sagemaker_endpoint[0].endpoint_name, null)
}
