terraform {
  required_version = ">= 1.6.0"

  # Configure after running infra/backend.
  # backend "s3" {
  #   bucket         = "replace-with-backend-bucket"
  #   key            = "aiops/stage/terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "aiops-terraform-locks"
  #   encrypt        = true
  # }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = local.common_tags
  }
}

