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

variable "enable_public_http_alb" {
  description = "Whether to create a temporary public HTTP-only ALB for stage/demo access."
  type        = bool
  default     = false
}

variable "alb_allowed_http_cidrs" {
  description = "CIDR blocks allowed to reach the optional demo ALB over HTTP."
  type        = list(string)
  default     = []

  validation {
    condition     = alltrue([for cidr in var.alb_allowed_http_cidrs : can(cidrhost(cidr, 0))])
    error_message = "alb_allowed_http_cidrs must contain valid CIDR blocks."
  }
}

variable "alb_subnet_ids" {
  description = "Optional subnet IDs for the public demo ALB. If empty, automatically selected VPC subnets are used."
  type        = list(string)
  default     = []
}

variable "instance_type" {
  description = "EC2 instance type for the monitored workload."
  type        = string
  default     = "t3.medium"
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

variable "allowed_availability_zones" {
  description = "Optional AZ allow-list for automatic subnet selection. If empty, Terraform uses AZs where the requested instance type is offered."
  type        = list(string)
  default     = []

  validation {
    condition     = alltrue([for az in var.allowed_availability_zones : can(regex("^[a-z]{2}-[a-z]+-[0-9][a-z]$", az))])
    error_message = "allowed_availability_zones entries must be valid availability zone names such as us-east-1a."
  }
}

variable "associate_public_ip_address" {
  description = "Whether to associate a public IP address with the workload instance."
  type        = bool
  default     = false
}

variable "ebs_optimized" {
  description = "Whether the workload instance should use EBS optimization."
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
  default     = 365

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
