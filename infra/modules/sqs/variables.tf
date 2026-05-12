variable "environment" {
  description = "Deployment environment name."
  type        = string
}

variable "name_prefix" {
  description = "Name prefix for SQS resources."
  type        = string
}

variable "visibility_timeout_seconds" {
  description = "SQS visibility timeout for remediation messages."
  type        = number
  default     = 900
}

variable "kms_key_arn" {
  description = "Optional KMS key ARN for SQS encryption."
  type        = string
  default     = null
}

variable "common_tags" {
  description = "Common tags to apply to resources."
  type        = map(string)
  default     = {}
}

