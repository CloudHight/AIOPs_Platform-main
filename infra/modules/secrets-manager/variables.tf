variable "environment" {
  description = "Deployment environment name."
  type        = string
}

variable "name_prefix" {
  description = "Name prefix for Secrets Manager resources."
  type        = string
}

variable "jira_secret_name" {
  description = "Optional explicit Jira credentials secret name. If null, a stable environment-scoped name is used."
  type        = string
  default     = null

  validation {
    condition     = var.jira_secret_name == null || can(regex("^[A-Za-z0-9/_+=.@-]{1,512}$", var.jira_secret_name))
    error_message = "jira_secret_name must be a valid Secrets Manager name using letters, numbers, /_+=.@- characters."
  }
}

variable "kms_key_arn" {
  description = "Optional KMS key ARN for Secrets Manager encryption."
  type        = string
  default     = null
}

variable "recovery_window_in_days" {
  description = "Secrets Manager deletion recovery window. Use 0 only for ephemeral dev environments."
  type        = number
  default     = 30

  validation {
    condition     = var.recovery_window_in_days == 0 || (var.recovery_window_in_days >= 7 && var.recovery_window_in_days <= 30)
    error_message = "recovery_window_in_days must be 0 for immediate deletion or between 7 and 30 days."
  }
}

variable "common_tags" {
  description = "Common tags to apply to resources."
  type        = map(string)
  default     = {}
}
