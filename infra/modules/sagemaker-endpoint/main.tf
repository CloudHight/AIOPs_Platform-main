data "aws_iam_policy_document" "sagemaker_assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["sagemaker.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

locals {
  raw_resource_prefix = "${var.name_prefix}-${var.environment}-${var.model_name}"
  normalized_resource_prefix = trim(
    replace(
      replace(local.raw_resource_prefix, "/[^A-Za-z0-9-]/", "-"),
      "/-+/",
      "-"
    ),
    "-"
  )
  resource_prefix_base = local.normalized_resource_prefix != "" ? local.normalized_resource_prefix : "aiops-model"
  resource_prefix_hash = substr(md5(local.raw_resource_prefix), 0, 8)
  # SageMaker endpoint configuration names are limited to 63 chars. Keep the shared
  # prefix short enough for "-endpoint-config" while preserving uniqueness.
  resource_prefix = (
    length(local.resource_prefix_base) <= 47
    ? local.resource_prefix_base
    : "${substr(local.resource_prefix_base, 0, 38)}-${local.resource_prefix_hash}"
  )
  execution_role_arn = (
    var.execution_role_arn != null
    ? var.execution_role_arn
    : aws_iam_role.sagemaker[0].arn
  )
}

resource "aws_iam_role" "sagemaker" {
  count = var.execution_role_arn == null ? 1 : 0

  name               = "${local.resource_prefix}-sagemaker-role"
  assume_role_policy = data.aws_iam_policy_document.sagemaker_assume_role.json

  tags = var.common_tags
}

resource "aws_iam_role_policy" "sagemaker_model_artifacts" {
  count = var.execution_role_arn == null ? 1 : 0

  name = "${local.resource_prefix}-model-artifacts"
  role = aws_iam_role.sagemaker[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::${split("/", replace(var.model_artifact_s3_uri, "s3://", ""))[0]}",
          "arn:aws:s3:::${replace(var.model_artifact_s3_uri, "s3://", "")}"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_sagemaker_model" "this" {
  name                     = "${local.resource_prefix}-model"
  execution_role_arn       = local.execution_role_arn
  enable_network_isolation = var.enable_network_isolation

  primary_container {
    image          = var.model_image_uri
    model_data_url = var.model_artifact_s3_uri
    environment    = var.model_environment
  }

  tags = var.common_tags
}

resource "aws_sagemaker_endpoint_configuration" "this" {
  name        = "${local.resource_prefix}-endpoint-config"
  kms_key_arn = var.kms_key_arn

  production_variants {
    variant_name           = "AllTraffic"
    model_name             = aws_sagemaker_model.this.name
    initial_instance_count = var.initial_instance_count
    instance_type          = var.instance_type
  }

  tags = var.common_tags
}

resource "aws_sagemaker_endpoint" "this" {
  name                 = "${local.resource_prefix}-endpoint"
  endpoint_config_name = aws_sagemaker_endpoint_configuration.this.name

  tags = var.common_tags
}

resource "aws_cloudwatch_metric_alarm" "model_5xx_errors" {
  count = length(var.alarm_actions) > 0 ? 1 : 0

  alarm_name          = "${local.resource_prefix}-model-5xx-errors"
  alarm_description   = "SageMaker endpoint model 5XX errors for ${var.model_name}"
  namespace           = "AWS/SageMaker"
  metric_name         = "Invocation5XXErrors"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = var.invocation_error_threshold
  comparison_operator = "GreaterThanOrEqualToThreshold"
  alarm_actions       = var.alarm_actions
  ok_actions          = var.alarm_actions

  dimensions = {
    EndpointName = aws_sagemaker_endpoint.this.name
    VariantName  = "AllTraffic"
  }

  tags = var.common_tags
}

resource "aws_cloudwatch_metric_alarm" "model_latency" {
  count = length(var.alarm_actions) > 0 ? 1 : 0

  alarm_name          = "${local.resource_prefix}-model-latency"
  alarm_description   = "SageMaker endpoint model latency for ${var.model_name}"
  namespace           = "AWS/SageMaker"
  metric_name         = "ModelLatency"
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 2
  threshold           = var.model_latency_threshold_microseconds
  comparison_operator = "GreaterThanThreshold"
  alarm_actions       = var.alarm_actions
  ok_actions          = var.alarm_actions

  dimensions = {
    EndpointName = aws_sagemaker_endpoint.this.name
    VariantName  = "AllTraffic"
  }

  tags = var.common_tags
}
