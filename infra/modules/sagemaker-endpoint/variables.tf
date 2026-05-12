variable "environment" {
  description = "Deployment environment name."
  type        = string
}

variable "name_prefix" {
  description = "Name prefix for SageMaker resources."
  type        = string
}

variable "model_name" {
  description = "Logical model name, for example cpu-rcf or nginx-bert."
  type        = string
}

variable "model_artifact_s3_uri" {
  description = "Approved immutable model artifact URI published by Jenkins."
  type        = string
}

variable "model_image_uri" {
  description = "SageMaker inference container image URI."
  type        = string
}

variable "instance_type" {
  description = "SageMaker endpoint instance type."
  type        = string
  default     = "ml.m5.large"
}

variable "initial_instance_count" {
  description = "Initial endpoint instance count."
  type        = number
  default     = 1
}

variable "execution_role_arn" {
  description = "Optional existing SageMaker execution role ARN. If null, this module creates one."
  type        = string
  default     = null
}

variable "enable_network_isolation" {
  description = "Whether SageMaker model network isolation is enabled."
  type        = bool
  default     = true
}

variable "model_environment" {
  description = "Environment variables for the SageMaker model container."
  type        = map(string)
  default     = {}
}

variable "kms_key_arn" {
  description = "Optional KMS key ARN for endpoint data capture/storage integrations."
  type        = string
  default     = null
}

variable "alarm_actions" {
  description = "Alarm action ARNs for SageMaker endpoint alarms."
  type        = list(string)
  default     = []
}

variable "invocation_error_threshold" {
  description = "Threshold for SageMaker invocation 5XX errors."
  type        = number
  default     = 1
}

variable "model_latency_threshold_microseconds" {
  description = "Threshold for average model latency in microseconds."
  type        = number
  default     = 5000000
}

variable "common_tags" {
  description = "Common tags to apply to resources."
  type        = map(string)
  default     = {}
}
