variable "aws_region" {
  description = "AWS region for this environment."
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment name."
  type        = string
  default     = "stage"

  validation {
    condition     = contains(["stage"], var.environment)
    error_message = "This root module is for the stage environment only."
  }
}

variable "project" {
  description = "Project tag value."
  type        = string
  default     = "AIOps"
}

variable "allowed_http_cidrs" {
  description = "CIDR blocks allowed to reach the workload over HTTP."
  type        = list(string)
  default     = []
}

variable "workload_instance_type" {
  description = "EC2 instance type for the monitored workload."
  type        = string
  default     = "t3.medium"
}

variable "workload_app_image" {
  description = "Container image URI for the monitored workload."
  type        = string
  default     = "cloudhight/testapp:latest"
}

variable "workload_associate_public_ip" {
  description = "Whether the workload instance should receive a public IP."
  type        = bool
  default     = false
}

variable "workload_log_retention_days" {
  description = "CloudWatch retention for Nginx workload logs."
  type        = number
  default     = 60
}

variable "enable_aiops_control_plane" {
  description = "Whether to deploy the AIOps control plane."
  type        = bool
  default     = false
}

variable "notification_email" {
  description = "Optional email endpoint for anomaly notifications."
  type        = string
  default     = null
}

variable "cpu_model_endpoint" {
  description = "CPU anomaly SageMaker endpoint name."
  type        = string
  default     = "cpu-anomaly-model-endpoint"
}

variable "log_model_endpoint" {
  description = "Log anomaly SageMaker endpoint name."
  type        = string
  default     = "log-anomaly-model-endpoint"
}

variable "jira_project_key" {
  description = "Jira project key for generated incidents."
  type        = string
  default     = "PROJ"
}

variable "monitoring_frequency" {
  description = "EventBridge schedule expression."
  type        = string
  default     = "rate(5 minutes)"
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

variable "enable_sagemaker_endpoints" {
  description = "Whether to deploy SageMaker endpoints from approved model artifacts."
  type        = bool
  default     = false
}

variable "model_version" {
  description = "Approved model version from Jenkins."
  type        = string
  default     = "local"
}

variable "cpu_model_artifact_s3_uri" {
  description = "Approved CPU RCF model artifact URI."
  type        = string
  default     = null
}

variable "log_model_artifact_s3_uri" {
  description = "Approved Nginx BERT model artifact URI."
  type        = string
  default     = null
}

variable "cpu_model_image_uri" {
  description = "CPU RCF SageMaker inference image URI."
  type        = string
  default     = null
}

variable "log_model_image_uri" {
  description = "Nginx BERT SageMaker inference image URI."
  type        = string
  default     = null
}

variable "cpu_endpoint_instance_type" {
  description = "Instance type for the CPU RCF endpoint."
  type        = string
  default     = "ml.m5.large"
}

variable "log_endpoint_instance_type" {
  description = "Instance type for the Nginx BERT endpoint."
  type        = string
  default     = "ml.g5.xlarge"
}
