module "ec2_workload" {
  source = "../../modules/ec2-workload"

  environment                 = var.environment
  name_prefix                 = "aiops"
  allowed_http_cidrs          = var.allowed_http_cidrs
  instance_type               = var.workload_instance_type
  app_image                   = var.workload_app_image
  associate_public_ip_address = var.workload_associate_public_ip
  log_retention_days          = var.workload_log_retention_days
  common_tags                 = local.common_tags
}

module "cpu_sagemaker_endpoint" {
  count  = var.enable_sagemaker_endpoints ? 1 : 0
  source = "../../modules/sagemaker-endpoint"

  environment           = var.environment
  name_prefix           = "aiops"
  model_name            = "cpu-rcf-${var.model_version}"
  model_artifact_s3_uri = var.cpu_model_artifact_s3_uri
  model_image_uri       = var.cpu_model_image_uri
  instance_type         = var.cpu_endpoint_instance_type
  alarm_actions         = []
  common_tags           = local.common_tags
}

module "log_sagemaker_endpoint" {
  count  = var.enable_sagemaker_endpoints ? 1 : 0
  source = "../../modules/sagemaker-endpoint"

  environment           = var.environment
  name_prefix           = "aiops"
  model_name            = "nginx-bert-${var.model_version}"
  model_artifact_s3_uri = var.log_model_artifact_s3_uri
  model_image_uri       = var.log_model_image_uri
  instance_type         = var.log_endpoint_instance_type
  alarm_actions         = []
  common_tags           = local.common_tags
}

module "aiops_control_plane" {
  count  = var.enable_aiops_control_plane ? 1 : 0
  source = "../../modules/aiops-control-plane"

  environment                  = var.environment
  name_prefix                  = "aiops"
  notification_email           = var.notification_email
  cpu_model_endpoint           = var.enable_sagemaker_endpoints ? module.cpu_sagemaker_endpoint[0].endpoint_name : var.cpu_model_endpoint
  log_model_endpoint           = var.enable_sagemaker_endpoints ? module.log_sagemaker_endpoint[0].endpoint_name : var.log_model_endpoint
  jira_project_key             = var.jira_project_key
  monitoring_frequency         = var.monitoring_frequency
  instance_tag_key             = "AnomalyMonitoring"
  instance_tag_value           = "enabled"
  cpu_threshold                = var.cpu_threshold
  log_threshold                = var.log_threshold
  grace_period_minutes         = var.grace_period_minutes
  auto_remediation_enabled     = var.auto_remediation_enabled
  dry_run                      = var.dry_run
  max_remediation_attempts     = var.max_remediation_attempts
  remediation_cooldown_minutes = var.remediation_cooldown_minutes
  lambda_artifact_bucket       = var.lambda_artifact_bucket
  lambda_artifact_key          = var.lambda_artifact_key
  lambda_artifact_version      = var.lambda_artifact_version
  lambda_source_code_hash      = var.lambda_source_code_hash
  lambda_local_package_path    = var.lambda_local_package_path
  nginx_log_group_arns = [
    module.ec2_workload.nginx_access_log_group_arn,
    module.ec2_workload.nginx_error_log_group_arn
  ]
  workload_instance_id        = module.ec2_workload.instance_id
  nginx_access_log_group_name = module.ec2_workload.nginx_access_log_group_name
  nginx_error_log_group_name  = module.ec2_workload.nginx_error_log_group_name
  common_tags                 = local.common_tags
}
