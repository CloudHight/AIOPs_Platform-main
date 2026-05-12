data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

locals {
  function_name = "${var.name_prefix}-anomaly-detection-${var.environment}"
  log_group_arns = length(var.nginx_log_group_arns) > 0 ? [
    for arn in var.nginx_log_group_arns : "${arn}:*"
    ] : [
    "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:nginx/*:*"
  ]
}

resource "aws_iam_role" "lambda" {
  name = "${local.function_name}-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = var.common_tags
}

resource "aws_iam_role_policy_attachment" "basic" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "lambda" {
  name = "${local.function_name}-policy"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:GetMetricData",
          "cloudwatch:GetMetricStatistics",
          "cloudwatch:ListMetrics"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "sagemaker:InvokeEndpoint"
        ]
        Resource = [
          "arn:aws:sagemaker:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:endpoint/${var.cpu_model_endpoint}",
          "arn:aws:sagemaker:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:endpoint/${var.log_model_endpoint}"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = var.jira_credentials_secret_arn
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:UpdateItem",
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:BatchWriteItem"
        ]
        Resource = [
          var.dynamodb_table_arn,
          "${var.dynamodb_table_arn}/index/*"
        ]
      },
      {
        Effect   = "Allow"
        Action   = "sns:Publish"
        Resource = var.sns_topic_arn
      },
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage",
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:ChangeMessageVisibility"
        ]
        Resource = [
          var.processing_queue_arn,
          var.dlq_arn
        ]
      },
      {
        Effect   = "Allow"
        Action   = "events:PutEvents"
        Resource = var.event_bus_arn
      },
      {
        Effect = "Allow"
        Action = [
          "ssm:ListCommands",
          "ssm:ListCommandInvocations"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters",
          "ssm:GetParametersByPath"
        ]
        Resource = "arn:aws:ssm:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:parameter/AnomalyDetection/${var.environment}/*"
      },
      {
        Effect   = "Allow"
        Action   = "ssm:SendCommand"
        Resource = "arn:aws:ssm:${data.aws_region.current.name}::document/AWS-RunShellScript"
      },
      {
        Effect   = "Allow"
        Action   = "ssm:SendCommand"
        Resource = "arn:aws:ec2:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:instance/*"
        Condition = {
          StringEquals = {
            "ssm:resourceTag/${var.instance_tag_key}" = var.instance_tag_value
            "ssm:resourceTag/Project"                 = "AIOPs"
          }
        }
      },
      {
        Effect = "Allow"
        Action = [
          "ec2:DescribeInstances",
          "ec2:DescribeTags"
        ]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = "ec2:RebootInstances"
        Resource = "arn:aws:ec2:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:instance/*"
        Condition = {
          StringEquals = {
            "ec2:ResourceTag/${var.instance_tag_key}" = var.instance_tag_value
            "ec2:ResourceTag/Project"                 = "AIOPs"
          }
        }
      },
      {
        Effect   = "Allow"
        Action   = "logs:DescribeLogGroups"
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:FilterLogEvents",
          "logs:DescribeLogStreams"
        ]
        Resource = local.log_group_arns
      }
    ]
  })
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${local.function_name}"
  retention_in_days = 30

  tags = var.common_tags
}

resource "aws_lambda_function" "anomaly_detection" {
  function_name = local.function_name
  description   = "Detects CPU and log anomalies, creates Jira tickets, and triggers auto-remediation"
  role          = aws_iam_role.lambda.arn
  handler       = var.handler
  runtime       = var.runtime
  timeout       = var.timeout_seconds
  memory_size   = var.memory_size_mb

  filename          = var.local_package_path
  s3_bucket         = var.lambda_artifact_bucket
  s3_key            = var.lambda_artifact_key
  s3_object_version = var.s3_object_version
  source_code_hash  = var.lambda_source_code_hash

  ephemeral_storage {
    size = var.ephemeral_storage_mb
  }

  tracing_config {
    mode = "Active"
  }

  environment {
    variables = {
      POWERTOOLS_SERVICE_NAME             = "anomaly-detection"
      LOG_LEVEL                           = "INFO"
      SOLUTION_VERSION                    = "1.0.0"
      ENVIRONMENT                         = var.environment
      DYNAMODB_TABLE                      = var.dynamodb_table_name
      SNS_TOPIC_ARN                       = var.sns_topic_arn
      PROCESSING_QUEUE_URL                = var.processing_queue_url
      DLQ_URL                             = var.dlq_url
      EVENT_BUS_NAME                      = var.event_bus_name
      CPU_MODEL_ENDPOINT                  = var.cpu_model_endpoint
      LOG_MODEL_ENDPOINT                  = var.log_model_endpoint
      ANOMALY_THRESHOLD_CPU               = tostring(var.cpu_threshold)
      ANOMALY_THRESHOLD_LOG               = tostring(var.log_threshold)
      GRACE_PERIOD_MINUTES                = tostring(var.grace_period_minutes)
      JIRA_PROJECT_KEY                    = var.jira_project_key
      JIRA_CREDENTIALS_SECRET             = var.jira_credentials_secret_arn
      INSTANCE_TAG_KEY                    = var.instance_tag_key
      INSTANCE_TAG_VALUE                  = var.instance_tag_value
      MONITORING_FREQUENCY                = var.monitoring_frequency
      AUTO_REMEDIATION_ENABLED            = tostring(var.auto_remediation_enabled)
      DRY_RUN                             = tostring(var.dry_run)
      MAX_REMEDIATION_ATTEMPTS            = tostring(var.max_remediation_attempts)
      REMEDIATION_COOLDOWN_MINUTES        = tostring(var.remediation_cooldown_minutes)
      ANOMALY_TTL_DAYS                    = "30"
      RUNBOOK_URL                         = "docs/operations-runbook.md"
      AWS_NODEJS_CONNECTION_REUSE_ENABLED = "1"
    }
  }

  tags = var.common_tags

  depends_on = [
    aws_cloudwatch_log_group.lambda,
    aws_iam_role_policy_attachment.basic,
    aws_iam_role_policy.lambda
  ]
}

resource "aws_lambda_event_source_mapping" "sqs" {
  event_source_arn                   = var.processing_queue_arn
  function_name                      = aws_lambda_function.anomaly_detection.arn
  batch_size                         = 10
  maximum_batching_window_in_seconds = 30
  enabled                            = true
}
