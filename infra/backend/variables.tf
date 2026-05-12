variable "aws_region" {
  description = "AWS region for the Terraform backend bootstrap resources."
  type        = string
  default     = "us-east-1"
}

variable "project" {
  description = "Project tag value."
  type        = string
  default     = "AIOps"
}

variable "environment" {
  description = "Environment tag for backend resources."
  type        = string
  default     = "shared"
}

variable "state_bucket_name" {
  description = "Globally unique S3 bucket name for Terraform remote state."
  type        = string

  validation {
    condition     = length(var.state_bucket_name) >= 3
    error_message = "state_bucket_name must be a valid S3 bucket name."
  }
}

variable "lock_table_name" {
  description = "DynamoDB table name for Terraform state locking."
  type        = string
  default     = "aiops-terraform-locks"
}

