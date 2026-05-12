variable "environment" {
  description = "Deployment environment name."
  type        = string
}

variable "name_prefix" {
  description = "Name prefix for EventBridge resources."
  type        = string
}

variable "monitoring_frequency" {
  description = "EventBridge schedule expression for anomaly detection."
  type        = string
  default     = "rate(5 minutes)"
}

variable "lambda_function_name" {
  description = "Lambda function name to invoke on schedule."
  type        = string
}

variable "lambda_function_arn" {
  description = "Lambda function ARN to invoke on schedule."
  type        = string
}

variable "sns_topic_arn" {
  description = "SNS topic ARN for anomaly event notifications."
  type        = string
}

variable "common_tags" {
  description = "Common tags to apply to resources."
  type        = map(string)
  default     = {}
}
