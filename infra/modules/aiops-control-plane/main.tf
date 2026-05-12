data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

locals {
  event_bus_name = "${var.name_prefix}-anomaly-events-${var.environment}"
  event_bus_arn  = "arn:aws:events:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:event-bus/${local.event_bus_name}"
}

module "dynamodb" {
  source = "../dynamodb"

  environment = var.environment
  name_prefix = var.name_prefix
  kms_key_arn = var.kms_key_arn
  common_tags = var.common_tags
}

module "sqs" {
  source = "../sqs"

  environment = var.environment
  name_prefix = var.name_prefix
  kms_key_arn = var.kms_key_arn
  common_tags = var.common_tags
}

module "sns" {
  source = "../sns"

  environment        = var.environment
  name_prefix        = var.name_prefix
  notification_email = var.notification_email
  kms_key_arn        = var.kms_key_arn
  common_tags        = var.common_tags
}

module "secrets_manager" {
  source = "../secrets-manager"

  environment = var.environment
  name_prefix = var.name_prefix
  kms_key_arn = var.kms_key_arn
  common_tags = var.common_tags
}

module "ssm_parameters" {
  source = "../ssm-parameters"

  environment                  = var.environment
  name_prefix                  = var.name_prefix
  cpu_threshold                = var.cpu_threshold
  log_threshold                = var.log_threshold
  grace_period_minutes         = var.grace_period_minutes
  auto_remediation_enabled     = var.auto_remediation_enabled
  dry_run                      = var.dry_run
  max_remediation_attempts     = var.max_remediation_attempts
  remediation_cooldown_minutes = var.remediation_cooldown_minutes
  common_tags                  = var.common_tags
}

module "lambda_function" {
  source = "../lambda-function"

  environment                  = var.environment
  name_prefix                  = var.name_prefix
  lambda_artifact_bucket       = var.lambda_artifact_bucket
  lambda_artifact_key          = var.lambda_artifact_key
  s3_object_version            = var.lambda_artifact_version
  lambda_source_code_hash      = var.lambda_source_code_hash
  local_package_path           = var.lambda_local_package_path
  dynamodb_table_name          = module.dynamodb.table_name
  dynamodb_table_arn           = module.dynamodb.table_arn
  sns_topic_arn                = module.sns.topic_arn
  processing_queue_url         = module.sqs.queue_url
  processing_queue_arn         = module.sqs.queue_arn
  dlq_url                      = module.sqs.dlq_url
  dlq_arn                      = module.sqs.dlq_arn
  event_bus_name               = local.event_bus_name
  event_bus_arn                = local.event_bus_arn
  cpu_model_endpoint           = var.cpu_model_endpoint
  log_model_endpoint           = var.log_model_endpoint
  jira_project_key             = var.jira_project_key
  jira_credentials_secret_arn  = module.secrets_manager.jira_secret_arn
  instance_tag_key             = var.instance_tag_key
  instance_tag_value           = var.instance_tag_value
  monitoring_frequency         = var.monitoring_frequency
  cpu_threshold                = var.cpu_threshold
  log_threshold                = var.log_threshold
  grace_period_minutes         = var.grace_period_minutes
  auto_remediation_enabled     = var.auto_remediation_enabled
  dry_run                      = var.dry_run
  max_remediation_attempts     = var.max_remediation_attempts
  remediation_cooldown_minutes = var.remediation_cooldown_minutes
  nginx_log_group_arns         = var.nginx_log_group_arns
  common_tags                  = var.common_tags
}

module "eventbridge" {
  source = "../eventbridge"

  environment          = var.environment
  name_prefix          = var.name_prefix
  monitoring_frequency = var.monitoring_frequency
  lambda_function_name = module.lambda_function.function_name
  lambda_function_arn  = module.lambda_function.function_arn
  sns_topic_arn        = module.sns.topic_arn
  common_tags          = var.common_tags
}

module "cloudwatch_observability" {
  source = "../cloudwatch-observability"

  environment                 = var.environment
  name_prefix                 = var.name_prefix
  lambda_function_name        = module.lambda_function.function_name
  dynamodb_table_name         = module.dynamodb.table_name
  sqs_queue_name              = module.sqs.queue_name
  sqs_dlq_name                = module.sqs.dlq_name
  sns_topic_arn               = module.sns.topic_arn
  workload_instance_id        = var.workload_instance_id
  nginx_access_log_group_name = var.nginx_access_log_group_name
  nginx_error_log_group_name  = var.nginx_error_log_group_name
  cpu_model_endpoint_name     = var.cpu_model_endpoint
  log_model_endpoint_name     = var.log_model_endpoint
  enable_managed_grafana      = var.enable_managed_grafana
  grafana_workspace_name      = var.grafana_workspace_name
  common_tags                 = var.common_tags
}
