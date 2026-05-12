locals {
  jenkins_instance_role_name = "${var.name_prefix}-${var.environment}-jenkins-role"

  common_tags = {
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "Terraform"
    Component   = "Jenkins"
  }
}
