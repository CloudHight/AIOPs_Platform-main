terraform {
  required_version = ">= 1.6.0"

  # Configure after running infra/backend if Jenkins state should be remote.
  backend "s3" {
    bucket         = "motiva-aiops-terraform-state"
    key            = "aiops/jenkins/terraform.tfstate"
    region         = "us-east-1"
    use_lockfile   = true
    # dynamodb_table = "motiva-aiops-terraform-locks"
    encrypt        = true
  }

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
