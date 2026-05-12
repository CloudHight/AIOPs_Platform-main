variable "environment" {
  description = "Deployment environment name."
  type        = string
}

variable "name_prefix" {
  description = "Name prefix for SSM parameter resources."
  type        = string
}

variable "cpu_threshold" {
  description = "CPU anomaly score threshold."
  type        = number
  default     = 0.5
}

variable "log_threshold" {
  description = "Log anomaly score threshold."
  type        = number
  default     = 0.8
}

variable "grace_period_minutes" {
  description = "Minutes to wait before auto-remediation."
  type        = number
  default     = 15
}

variable "auto_remediation_enabled" {
  description = "Whether automated remediation is enabled."
  type        = bool
  default     = false
}

variable "dry_run" {
  description = "Whether remediation runs in dry-run mode."
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

variable "kms_key_arn" {
  description = "KMS key ARN used to encrypt SecureString runtime parameters."
  type        = string
}

variable "common_tags" {
  description = "Common tags to apply to resources."
  type        = map(string)
  default     = {}
}
