variable "environment" {
  description = "Environment name for the Jenkins controller stack."
  type        = string
  default     = "tools"
}

variable "name_prefix" {
  description = "Name prefix for Jenkins controller resources."
  type        = string
  default     = "aiops"
}

variable "instance_type" {
  description = "EC2 instance type for the Jenkins controller."
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
  description = "Whether the Jenkins controller should receive a public IP."
  type        = bool
  default     = false
}

variable "allowed_jenkins_cidrs" {
  description = "CIDR blocks allowed to reach Jenkins over HTTP 8080. Empty means no inbound Jenkins UI access."
  type        = list(string)
  default     = []

  validation {
    condition     = alltrue([for cidr in var.allowed_jenkins_cidrs : can(cidrhost(cidr, 0))])
    error_message = "allowed_jenkins_cidrs must contain valid CIDR blocks."
  }
}

variable "root_volume_size_gb" {
  description = "Root EBS volume size in GiB."
  type        = number
  default     = 40
}

variable "jenkins_home_volume_size_gb" {
  description = "Dedicated Jenkins home EBS volume size in GiB."
  type        = number
  default     = 100
}

variable "jenkins_home_device_name" {
  description = "Device name for the Jenkins home EBS volume."
  type        = string
  default     = "/dev/xvdf"
}

variable "allowed_deploy_role_arns" {
  description = "AWS deploy role ARNs the Jenkins instance role may assume."
  type        = list(string)
  default     = []
}

variable "artifact_bucket_arns" {
  description = "S3 bucket ARNs Jenkins can use for Lambda and model artifacts."
  type        = list(string)
  default     = []
}

variable "common_tags" {
  description = "Common tags to apply to Jenkins resources."
  type        = map(string)
  default     = {}
}
