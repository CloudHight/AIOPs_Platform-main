output "module_name" {
  description = "Module identifier."
  value       = "ec2-workload"
}

output "instance_id" {
  description = "Monitored workload instance ID."
  value       = aws_instance.workload.id
}

output "instance_private_ip" {
  description = "Private IP address of the monitored workload instance."
  value       = aws_instance.workload.private_ip
}

output "instance_public_ip" {
  description = "Public IP address of the monitored workload instance, if associated."
  value       = aws_instance.workload.public_ip
}

output "security_group_id" {
  description = "Security group ID for the workload."
  value       = aws_security_group.workload.id
}

output "instance_profile_name" {
  description = "IAM instance profile name for the workload."
  value       = aws_iam_instance_profile.workload.name
}

output "role_arn" {
  description = "IAM role ARN for the workload."
  value       = aws_iam_role.workload.arn
}

output "nginx_access_log_group_name" {
  description = "CloudWatch log group name for Nginx access logs."
  value       = aws_cloudwatch_log_group.nginx_access.name
}

output "nginx_access_log_group_arn" {
  description = "CloudWatch log group ARN for Nginx access logs."
  value       = aws_cloudwatch_log_group.nginx_access.arn
}

output "nginx_error_log_group_name" {
  description = "CloudWatch log group name for Nginx error logs."
  value       = aws_cloudwatch_log_group.nginx_error.name
}

output "nginx_error_log_group_arn" {
  description = "CloudWatch log group ARN for Nginx error logs."
  value       = aws_cloudwatch_log_group.nginx_error.arn
}
