variable "environment" {
  description = "Deployment environment name."
  type        = string

  validation {
    condition     = contains(["dev", "stage", "prod"], var.environment)
    error_message = "environment must be one of dev, stage, or prod."
  }
}

variable "name_prefix" {
  description = "Name prefix for EC2 workload resources."
  type        = string

  validation {
    condition     = length(var.name_prefix) > 0
    error_message = "name_prefix must not be empty."
  }
}

variable "allowed_http_cidrs" {
  description = "CIDR blocks allowed to reach the workload over HTTP."
  type        = list(string)
  default     = []

  validation {
    condition     = alltrue([for cidr in var.allowed_http_cidrs : can(cidrhost(cidr, 0))])
    error_message = "allowed_http_cidrs must contain valid CIDR blocks."
  }
}

variable "instance_type" {
  description = "EC2 instance type for the monitored workload."
  type        = string
  default     = "t2.medium"
}

variable "app_image" {
  description = "Container image URI for the workload."
  type        = string
  default     = "cloudhight/testapp:latest"
}

variable "vpc_id" {
  description = "VPC ID for the workload. If null, the default VPC is used for migration compatibility."
  type        = string
  default     = null
}

variable "subnet_id" {
  description = "Subnet ID for the workload. If null, the first subnet in the selected VPC is used."
  type        = string
  default     = null
}

variable "associate_public_ip_address" {
  description = "Whether to associate a public IP address with the workload instance."
  type        = bool
  default     = true
}

variable "monitoring_tag_key" {
  description = "Tag key used by the AIOps Lambda to discover monitored instances."
  type        = string
  default     = "AnomalyMonitoring"
}

variable "monitoring_tag_value" {
  description = "Tag value used by the AIOps Lambda to discover monitored instances."
  type        = string
  default     = "enabled"
}

variable "log_retention_days" {
  description = "CloudWatch retention for Nginx workload logs."
  type        = number
  default     = 30

  validation {
    condition     = contains([7, 14, 30, 60, 90, 180, 365, 731, 1827, 3653], var.log_retention_days)
    error_message = "log_retention_days must be a valid CloudWatch Logs retention value."
  }
}

variable "cloudwatch_log_kms_key_id" {
  description = "Optional KMS key ID/ARN for workload CloudWatch log groups."
  type        = string
  default     = null
}

variable "nginx_access_log_group_name" {
  description = "CloudWatch log group name for Nginx access logs."
  type        = string
  default     = "nginx/access.log"
}

variable "nginx_error_log_group_name" {
  description = "CloudWatch log group name for Nginx error logs."
  type        = string
  default     = "nginx/error.log"
}

variable "common_tags" {
  description = "Common tags to apply to resources."
  type        = map(string)
  default     = {}
}
