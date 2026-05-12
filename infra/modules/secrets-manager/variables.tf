variable "environment" {
  description = "Deployment environment name."
  type        = string
}

variable "name_prefix" {
  description = "Name prefix for Secrets Manager resources."
  type        = string
}

variable "kms_key_arn" {
  description = "Optional KMS key ARN for Secrets Manager encryption."
  type        = string
  default     = null
}

variable "common_tags" {
  description = "Common tags to apply to resources."
  type        = map(string)
  default     = {}
}

