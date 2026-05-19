variable "aws_region" {
  description = "AWS region for the Jenkins controller."
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name for the Jenkins controller stack."
  type        = string
  default     = "tools"
}

variable "project" {
  description = "Project tag value."
  type        = string
  default     = "AIOps"
}

variable "name_prefix" {
  description = "Name prefix for Jenkins resources."
  type        = string
  default     = "aiops"
}

variable "instance_type" {
  description = "EC2 instance type for Jenkins."
  type        = string
  default     = "t3.medium"
}

variable "vpc_id" {
  description = "VPC ID for Jenkins. If null, the default VPC is used."
  type        = string
  default     = null
}

variable "subnet_id" {
  description = "Subnet ID for Jenkins. If null, Terraform selects a subnet in the selected VPC where the requested instance type is offered."
  type        = string
  default     = null
}

variable "associate_public_ip_address" {
  description = "Whether Jenkins should receive a public IP."
  type        = bool
  default     = true
}

variable "allowed_jenkins_cidrs" {
  description = "CIDRs allowed to reach Jenkins on port 8080."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "root_volume_size_gb" {
  description = "Root volume size in GiB."
  type        = number
  default     = 100
}

variable "jenkins_home_volume_size_gb" {
  description = "Jenkins home volume size in GiB."
  type        = number
  default     = 300
}

variable "allowed_deploy_role_arns" {
  description = "Additional pre-existing deploy role ARNs Jenkins may assume."
  type        = list(string)
  default     = []
}

variable "create_deploy_roles" {
  description = "Whether this stack should create Jenkins deploy roles for the application environments."
  type        = bool
  default     = true
}

variable "deploy_role_environments" {
  description = "Application environments that should receive Jenkins deploy roles."
  type        = set(string)
  default     = ["dev", "stage", "prod"]

  validation {
    condition     = alltrue([for env in var.deploy_role_environments : can(regex("^[a-z0-9-]+$", env))])
    error_message = "deploy_role_environments values must use lowercase letters, numbers, and hyphens only."
  }
}

variable "deploy_role_max_session_duration" {
  description = "Maximum session duration, in seconds, for Jenkins deploy roles."
  type        = number
  default     = 3600

  validation {
    condition     = var.deploy_role_max_session_duration >= 3600 && var.deploy_role_max_session_duration <= 43200
    error_message = "deploy_role_max_session_duration must be between 3600 and 43200 seconds."
  }
}

variable "deploy_role_extra_policy_arns" {
  description = "Additional managed policy ARNs to attach to each Jenkins deploy role."
  type        = list(string)
  default     = []
}

variable "artifact_bucket_arns" {
  description = "Artifact bucket ARNs Jenkins may read/write."
  type        = list(string)
  default     = []
}
