variable "environment" {
  description = "Deployment environment name."
  type        = string
}

variable "name_prefix" {
  description = "Name prefix for SNS resources."
  type        = string
}

variable "notification_email" {
  description = "Optional email endpoint for anomaly notifications."
  type        = string
  default     = null
}

variable "kms_key_arn" {
  description = "Optional KMS key ARN for SNS encryption."
  type        = string
  default     = null
}

variable "common_tags" {
  description = "Common tags to apply to resources."
  type        = map(string)
  default     = {}
}

