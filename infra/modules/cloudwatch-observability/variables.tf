variable "environment" {
  description = "Deployment environment name."
  type        = string
}

variable "name_prefix" {
  description = "Name prefix for observability resources."
  type        = string
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days."
  type        = number
  default     = 30

  validation {
    condition     = contains([7, 14, 30, 60, 90, 180, 365, 731, 1827, 3653], var.log_retention_days)
    error_message = "log_retention_days must be a valid CloudWatch retention value."
  }
}

variable "common_tags" {
  description = "Common tags to apply to resources."
  type        = map(string)
  default     = {}
}

variable "lambda_function_name" {
  description = "AIOps Lambda function name."
  type        = string
}

variable "dynamodb_table_name" {
  description = "Anomaly DynamoDB table name."
  type        = string
}

variable "sqs_queue_name" {
  description = "Remediation queue name."
  type        = string
}

variable "sqs_dlq_name" {
  description = "Remediation DLQ name."
  type        = string
}

variable "sns_topic_arn" {
  description = "SNS topic ARN for alarm actions."
  type        = string
}

variable "lambda_timeout_seconds" {
  description = "Configured Lambda timeout in seconds."
  type        = number
  default     = 900
}

variable "workload_instance_id" {
  description = "Monitored workload EC2 instance ID."
  type        = string
  default     = null
}

variable "enable_workload_status_alarm" {
  description = "Whether to create the EC2 status-check alarm for the monitored workload."
  type        = bool
  default     = true
}

variable "nginx_access_log_group_name" {
  description = "Nginx access log group name."
  type        = string
  default     = null
}

variable "nginx_error_log_group_name" {
  description = "Nginx error log group name."
  type        = string
  default     = null
}

variable "cpu_model_endpoint_name" {
  description = "CPU SageMaker endpoint name."
  type        = string
  default     = null
}

variable "log_model_endpoint_name" {
  description = "Log SageMaker endpoint name."
  type        = string
  default     = null
}

variable "enable_managed_grafana" {
  description = "Whether to create an AWS Managed Grafana workspace."
  type        = bool
  default     = false
}

variable "grafana_workspace_name" {
  description = "Base name for the AWS Managed Grafana workspace."
  type        = string
  default     = "anomaly-ops"
}
