variable "environment" {
  description = "Deployment environment name."
  type        = string
}

variable "aws_partition" {
  description = "AWS partition for deterministic ARN construction."
  type        = string
  default     = "aws"

  validation {
    condition     = contains(["aws", "aws-us-gov", "aws-cn"], var.aws_partition)
    error_message = "aws_partition must be one of aws, aws-us-gov, or aws-cn."
  }
}

variable "aws_region" {
  description = "AWS region for deterministic ARN construction."
  type        = string
}

variable "aws_account_id" {
  description = "AWS account ID for deterministic ARN construction."
  type        = string

  validation {
    condition     = can(regex("^[0-9]{12}$", var.aws_account_id))
    error_message = "aws_account_id must be a 12-digit AWS account ID."
  }
}

variable "name_prefix" {
  description = "Name prefix for Lambda resources."
  type        = string
}

variable "lambda_artifact_bucket" {
  description = "S3 bucket containing the packaged Lambda artifact."
  type        = string
  default     = null
}

variable "lambda_artifact_key" {
  description = "S3 key for the packaged Lambda artifact."
  type        = string
  default     = null
}

variable "lambda_source_code_hash" {
  description = "Base64-encoded Lambda source package hash."
  type        = string
  default     = null
}

variable "handler" {
  description = "Lambda handler."
  type        = string
  default     = "aiops.handler.lambda_handler"
}

variable "runtime" {
  description = "Lambda runtime."
  type        = string
  default     = "python3.12"
}

variable "timeout_seconds" {
  description = "Lambda timeout in seconds."
  type        = number
  default     = 900
}

variable "memory_size_mb" {
  description = "Lambda memory size in MB."
  type        = number
  default     = 1024
}

variable "ephemeral_storage_mb" {
  description = "Lambda ephemeral storage size in MB."
  type        = number
  default     = 512
}

variable "reserved_concurrent_executions" {
  description = "Reserved concurrency for the anomaly detection Lambda."
  type        = number
  default     = 5
}

variable "log_retention_days" {
  description = "CloudWatch retention for Lambda logs."
  type        = number
  default     = 365

  validation {
    condition     = contains([7, 14, 30, 60, 90, 180, 365, 731, 1827, 3653], var.log_retention_days)
    error_message = "log_retention_days must be a valid CloudWatch Logs retention value."
  }
}

variable "kms_key_arn" {
  description = "Optional KMS key ARN for Lambda logs and SecureString parameter reads."
  type        = string
  default     = null
}

variable "lambda_environment_kms_key_arn" {
  description = "Optional real KMS key ARN for Lambda environment variable encryption. Lambda CreateGrant does not support alias ARNs."
  type        = string
  default     = null
}

variable "s3_object_version" {
  description = "Optional version ID for S3 Lambda artifact."
  type        = string
  default     = null
}

variable "local_package_path" {
  description = "Optional local Lambda zip path for dev plans."
  type        = string
  default     = null
}

variable "dynamodb_table_name" {
  description = "Anomaly table name."
  type        = string
}

variable "dynamodb_table_arn" {
  description = "Anomaly table ARN."
  type        = string
}

variable "sns_topic_arn" {
  description = "SNS notification topic ARN."
  type        = string
}

variable "processing_queue_url" {
  description = "Remediation queue URL."
  type        = string
}

variable "dlq_url" {
  description = "Dead-letter queue URL."
  type        = string
}

variable "event_bus_name" {
  description = "AIOps EventBridge bus name."
  type        = string
}

variable "event_bus_arn" {
  description = "AIOps EventBridge bus ARN."
  type        = string
}

variable "cpu_model_endpoint" {
  description = "CPU anomaly SageMaker endpoint name."
  type        = string
}

variable "log_model_endpoint" {
  description = "Log anomaly SageMaker endpoint name."
  type        = string
}

variable "jira_project_key" {
  description = "Jira project key."
  type        = string
}

variable "jira_credentials_secret_arn" {
  description = "Jira credentials secret ARN."
  type        = string
}

variable "instance_tag_key" {
  description = "EC2 tag key for monitored instances."
  type        = string
  default     = "AnomalyMonitoring"
}

variable "instance_tag_value" {
  description = "EC2 tag value for monitored instances."
  type        = string
  default     = "enabled"
}

variable "monitoring_frequency" {
  description = "Monitoring frequency expression, exposed to Lambda for compatibility."
  type        = string
  default     = "rate(5 minutes)"
}

variable "cpu_threshold" {
  description = "CPU anomaly threshold."
  type        = number
}

variable "log_threshold" {
  description = "Log anomaly threshold."
  type        = number
}

variable "grace_period_minutes" {
  description = "Grace period before remediation."
  type        = number
}

variable "auto_remediation_enabled" {
  description = "Whether remediation is enabled."
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

variable "nginx_log_group_arns" {
  description = "CloudWatch log group ARNs for Nginx logs."
  type        = list(string)
  default     = []
}

variable "common_tags" {
  description = "Common tags to apply to resources."
  type        = map(string)
  default     = {}
}
