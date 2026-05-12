output "jenkins_instance_id" {
  description = "Jenkins controller instance ID."
  value       = module.jenkins_controller.instance_id
}

output "jenkins_private_ip" {
  description = "Jenkins controller private IP."
  value       = module.jenkins_controller.private_ip
}

output "jenkins_public_ip" {
  description = "Jenkins controller public IP, if associated."
  value       = module.jenkins_controller.public_ip
}

output "jenkins_url" {
  description = "Jenkins URL when public access is enabled."
  value       = module.jenkins_controller.jenkins_url
}

output "jenkins_security_group_id" {
  description = "Jenkins security group ID."
  value       = module.jenkins_controller.security_group_id
}

output "jenkins_iam_role_arn" {
  description = "Jenkins instance IAM role ARN."
  value       = module.jenkins_controller.iam_role_arn
}

output "jenkins_deploy_role_arns" {
  description = "Deploy role ARNs created for Jenkins by environment."
  value = {
    for environment, role in aws_iam_role.jenkins_deploy : environment => role.arn
  }
}

output "jenkins_deploy_role_names" {
  description = "Deploy role names created for Jenkins by environment."
  value = {
    for environment, role in aws_iam_role.jenkins_deploy : environment => role.name
  }
}

output "ssm_start_session_command" {
  description = "SSM command to start an administration session on the Jenkins controller."
  value       = module.jenkins_controller.ssm_start_session_command
}
