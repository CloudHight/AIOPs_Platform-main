output "instance_id" {
  description = "Jenkins controller instance ID."
  value       = aws_instance.jenkins.id
}

output "private_ip" {
  description = "Jenkins controller private IP."
  value       = aws_instance.jenkins.private_ip
}

output "public_ip" {
  description = "Jenkins controller public IP, if associated."
  value       = aws_instance.jenkins.public_ip
}

output "security_group_id" {
  description = "Jenkins controller security group ID."
  value       = aws_security_group.jenkins.id
}

output "iam_role_arn" {
  description = "Jenkins controller IAM role ARN."
  value       = aws_iam_role.jenkins.arn
}

output "instance_profile_name" {
  description = "Jenkins controller instance profile name."
  value       = aws_iam_instance_profile.jenkins.name
}

output "jenkins_url" {
  description = "Jenkins HTTP URL when public access is enabled."
  value       = var.associate_public_ip_address ? "http://${aws_instance.jenkins.public_ip}:8080" : null
}

output "ssm_start_session_command" {
  description = "SSM command to start an administration session on the Jenkins controller."
  value       = "aws ssm start-session --target ${aws_instance.jenkins.id}"
}
