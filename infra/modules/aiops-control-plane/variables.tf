variable "environment" {
  description = "Deployment environment name."
  type        = string
}

variable "name_prefix" {
  description = "Name prefix for AIOps control-plane resources."
  type        = string
}

variable "common_tags" {
  description = "Common tags to apply to resources."
  type        = map(string)
  default     = {}
}

variable "notification_email" {
  description = "Email endpoint for SNS anomaly notifications."
  type        = string
  default     = null
}

variable "cpu_model_endpoint" {
  description = "SageMaker endpoint name for CPU anomaly detection."
  type        = string
}

variable "log_model_endpoint" {
  description = "SageMaker endpoint name for log anomaly detection."
  type        = string
}

variable "jira_project_key" {
  description = "Jira project key for generated incidents."
  type        = string
}

variable "monitoring_frequency" {
  description = "EventBridge schedule expression."
  type        = string
  default     = "rate(5 minutes)"
}

variable "instance_tag_key" {
  description = "EC2 tag key used for monitored instance discovery."
  type        = string
  default     = "AnomalyMonitoring"
}

variable "instance_tag_value" {
  description = "EC2 tag value used for monitored instance discovery."
  type        = string
  default     = "enabled"
}

variable "cpu_threshold" {
  description = "CPU anomaly threshold."
  type        = number
  default     = 0.85
}

variable "log_threshold" {
  description = "Log anomaly threshold."
  type        = number
  default     = 0.8
}

variable "grace_period_minutes" {
  description = "Minutes to wait before remediation."
  type        = number
  default     = 15
}

variable "auto_remediation_enabled" {
  description = "Whether automated remediation is enabled."
  type        = bool
  default     = false
}

variable "dry_run" {
  description = "Whether remediation is dry-run."
  type        = bool
  default     = true
}

variable "max_remediation_attempts" {
  description = "Maximum remediation attempts per open anomaly."
  type        = number
  default     = 1
}

variable "remediation_cooldown_minutes" {
  description = "Cooldown window between remediation attempts."
  type        = number
  default     = 60
}

variable "lambda_artifact_bucket" {
  description = "S3 bucket containing the Lambda package."
  type        = string
  default     = null
}

variable "lambda_artifact_key" {
  description = "S3 key for the Lambda package."
  type        = string
  default     = null
}

variable "lambda_artifact_version" {
  description = "Optional S3 object version for the Lambda package."
  type        = string
  default     = null
}

variable "lambda_source_code_hash" {
  description = "Base64-encoded hash of the Lambda package."
  type        = string
  default     = null
}

variable "lambda_local_package_path" {
  description = "Optional local Lambda package path."
  type        = string
  default     = null
}

variable "kms_key_arn" {
  description = "Optional KMS key ARN for encrypted services."
  type        = string
  default     = null
}

variable "nginx_log_group_arns" {
  description = "Nginx log group ARNs readable by Lambda."
  type        = list(string)
  default     = []
}

variable "workload_instance_id" {
  description = "Monitored workload EC2 instance ID for observability."
  type        = string
  default     = null
}

variable "nginx_access_log_group_name" {
  description = "Nginx access log group name for observability."
  type        = string
  default     = null
}

variable "nginx_error_log_group_name" {
  description = "Nginx error log group name for observability."
  type        = string
  default     = null
}

variable "enable_managed_grafana" {
  description = "Whether to create AWS Managed Grafana."
  type        = bool
  default     = false
}

variable "grafana_workspace_name" {
  description = "Base name for AWS Managed Grafana."
  type        = string
  default     = "anomaly-ops"
}
