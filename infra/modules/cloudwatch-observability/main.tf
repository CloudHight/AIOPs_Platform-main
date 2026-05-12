data "aws_region" "current" {}

locals {
  alarm_actions              = [var.sns_topic_arn]
  lambda_duration_threshold  = var.lambda_timeout_seconds * 1000 * 0.8
  has_workload_instance      = var.workload_instance_id != null && var.workload_instance_id != ""
  has_nginx_access_log_group = var.nginx_access_log_group_name != null && var.nginx_access_log_group_name != ""
  has_nginx_error_log_group  = var.nginx_error_log_group_name != null && var.nginx_error_log_group_name != ""
  sagemaker_metrics = compact([
    var.cpu_model_endpoint_name,
    var.log_model_endpoint_name
  ])
}

resource "aws_cloudwatch_log_metric_filter" "nginx_errors" {
  count = local.has_nginx_error_log_group ? 1 : 0

  name           = "${var.name_prefix}-nginx-errors-${var.environment}"
  log_group_name = var.nginx_error_log_group_name
  pattern        = "?ERROR ?Error ?error ?Exception ?exception ?timeout ?upstream ?500 ?502 ?503 ?504"

  metric_transformation {
    name          = "NginxErrorEvents"
    namespace     = "AIOps/${var.environment}"
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "${var.name_prefix}-lambda-errors-${var.environment}"
  alarm_description   = "AIOps Lambda errors are greater than zero"
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"

  dimensions = {
    FunctionName = var.lambda_function_name
  }

  alarm_actions = local.alarm_actions
  ok_actions    = local.alarm_actions

  tags = var.common_tags
}

resource "aws_cloudwatch_metric_alarm" "lambda_throttles" {
  alarm_name          = "${var.name_prefix}-lambda-throttles-${var.environment}"
  alarm_description   = "AIOps Lambda throttles are greater than zero"
  namespace           = "AWS/Lambda"
  metric_name         = "Throttles"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"

  dimensions = {
    FunctionName = var.lambda_function_name
  }

  alarm_actions = local.alarm_actions
  ok_actions    = local.alarm_actions

  tags = var.common_tags
}

resource "aws_cloudwatch_metric_alarm" "lambda_duration" {
  alarm_name          = "${var.name_prefix}-lambda-duration-${var.environment}"
  alarm_description   = "AIOps Lambda duration is approaching timeout"
  namespace           = "AWS/Lambda"
  metric_name         = "Duration"
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 2
  threshold           = local.lambda_duration_threshold
  comparison_operator = "GreaterThanThreshold"

  dimensions = {
    FunctionName = var.lambda_function_name
  }

  alarm_actions = local.alarm_actions
  ok_actions    = local.alarm_actions

  tags = var.common_tags
}

resource "aws_cloudwatch_metric_alarm" "dlq_messages" {
  alarm_name          = "${var.name_prefix}-anomaly-dlq-alarm-${var.environment}"
  alarm_description   = "Alert when anomaly remediation DLQ has messages"
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanThreshold"

  dimensions = {
    QueueName = var.sqs_dlq_name
  }

  alarm_actions = local.alarm_actions
  ok_actions    = local.alarm_actions

  tags = var.common_tags
}

resource "aws_cloudwatch_metric_alarm" "processing_queue_age" {
  alarm_name          = "${var.name_prefix}-queue-oldest-message-age-${var.environment}"
  alarm_description   = "AIOps remediation queue oldest message age is high"
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateAgeOfOldestMessage"
  statistic           = "Maximum"
  period              = 300
  evaluation_periods  = 2
  threshold           = 1800
  comparison_operator = "GreaterThanThreshold"

  dimensions = {
    QueueName = var.sqs_queue_name
  }

  alarm_actions = local.alarm_actions
  ok_actions    = local.alarm_actions

  tags = var.common_tags
}

resource "aws_cloudwatch_metric_alarm" "dynamodb_throttles" {
  alarm_name          = "${var.name_prefix}-dynamodb-throttles-${var.environment}"
  alarm_description   = "Anomaly DynamoDB table has throttled requests"
  namespace           = "AWS/DynamoDB"
  metric_name         = "ThrottledRequests"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"

  dimensions = {
    TableName = var.dynamodb_table_name
  }

  alarm_actions = local.alarm_actions
  ok_actions    = local.alarm_actions

  tags = var.common_tags
}

resource "aws_cloudwatch_metric_alarm" "ec2_status_check_failed" {
  count = local.has_workload_instance ? 1 : 0

  alarm_name          = "${var.name_prefix}-workload-status-check-${var.environment}"
  alarm_description   = "Monitored workload EC2 status check failed"
  namespace           = "AWS/EC2"
  metric_name         = "StatusCheckFailed"
  statistic           = "Maximum"
  period              = 300
  evaluation_periods  = 2
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"

  dimensions = {
    InstanceId = var.workload_instance_id
  }

  alarm_actions = local.alarm_actions
  ok_actions    = local.alarm_actions

  tags = var.common_tags
}

resource "aws_cloudwatch_metric_alarm" "nginx_error_volume" {
  count = local.has_nginx_error_log_group ? 1 : 0

  alarm_name          = "${var.name_prefix}-nginx-error-volume-${var.environment}"
  alarm_description   = "Nginx error log volume is elevated"
  namespace           = "AIOps/${var.environment}"
  metric_name         = "NginxErrorEvents"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 5
  comparison_operator = "GreaterThanThreshold"

  alarm_actions = local.alarm_actions
  ok_actions    = local.alarm_actions

  tags = var.common_tags

  depends_on = [
    aws_cloudwatch_log_metric_filter.nginx_errors
  ]
}

resource "aws_cloudwatch_dashboard" "aiops" {
  dashboard_name = "${var.name_prefix}-AnomalyDetection-${var.environment}"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        width  = 24
        height = 6
        properties = {
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", var.lambda_function_name, { stat = "Sum", label = "Lambda Invocations" }],
            ["AWS/Lambda", "Errors", "FunctionName", var.lambda_function_name, { stat = "Sum", label = "Lambda Errors" }],
            ["AWS/Lambda", "Duration", "FunctionName", var.lambda_function_name, { stat = "Average", label = "Avg Duration" }],
            ["AWS/Lambda", "Throttles", "FunctionName", var.lambda_function_name, { stat = "Sum", label = "Throttles" }]
          ]
          view    = "timeSeries"
          stacked = false
          region  = data.aws_region.current.name
          title   = "Lambda Performance"
          period  = 300
        }
      },
      {
        type   = "metric"
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", var.sqs_queue_name],
            ["AWS/SQS", "ApproximateNumberOfMessagesNotVisible", "QueueName", var.sqs_queue_name],
            ["AWS/SQS", "ApproximateAgeOfOldestMessage", "QueueName", var.sqs_queue_name, { label = "Oldest Message Age" }],
            ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", var.sqs_dlq_name, { label = "DLQ Messages" }]
          ]
          view    = "timeSeries"
          stacked = false
          region  = data.aws_region.current.name
          title   = "SQS Queue Metrics"
          period  = 300
        }
      },
      {
        type   = "metric"
        width  = 12
        height = 6
        properties = {
          metrics = [
            ["AWS/DynamoDB", "ConsumedReadCapacityUnits", "TableName", var.dynamodb_table_name],
            ["AWS/DynamoDB", "ConsumedWriteCapacityUnits", "TableName", var.dynamodb_table_name],
            ["AWS/DynamoDB", "SuccessfulRequestLatency", "TableName", var.dynamodb_table_name, "Operation", "PutItem", { label = "PutItem Latency" }],
            ["AWS/DynamoDB", "ThrottledRequests", "TableName", var.dynamodb_table_name, { stat = "Sum", label = "Throttles" }]
          ]
          view    = "timeSeries"
          stacked = false
          region  = data.aws_region.current.name
          title   = "DynamoDB Performance"
          period  = 300
        }
      },
      {
        type   = "metric"
        width  = 12
        height = 6
        properties = {
          metrics = concat(
            local.has_workload_instance ? [
              ["AWS/EC2", "CPUUtilization", "InstanceId", var.workload_instance_id, { stat = "Average", label = "CPU Utilization" }],
              ["AWS/EC2", "StatusCheckFailed", "InstanceId", var.workload_instance_id, { stat = "Maximum", label = "Status Check Failed" }]
            ] : [],
            local.has_nginx_error_log_group ? [
              ["AIOps/${var.environment}", "NginxErrorEvents", { stat = "Sum", label = "Nginx Error Events" }]
            ] : []
          )
          view    = "timeSeries"
          stacked = false
          region  = data.aws_region.current.name
          title   = "Workload Health"
          period  = 300
        }
      },
      {
        type   = "metric"
        width  = 12
        height = 6
        properties = {
          metrics = concat(
            [for endpoint_name in local.sagemaker_metrics : ["AWS/SageMaker", "Invocations", "EndpointName", endpoint_name, "VariantName", "AllTraffic", { stat = "Sum", label = "${endpoint_name} Invocations" }]],
            [for endpoint_name in local.sagemaker_metrics : ["AWS/SageMaker", "ModelLatency", "EndpointName", endpoint_name, "VariantName", "AllTraffic", { stat = "Average", label = "${endpoint_name} Latency" }]],
            [for endpoint_name in local.sagemaker_metrics : ["AWS/SageMaker", "Invocation4XXErrors", "EndpointName", endpoint_name, "VariantName", "AllTraffic", { stat = "Sum", label = "${endpoint_name} 4XX" }]],
            [for endpoint_name in local.sagemaker_metrics : ["AWS/SageMaker", "Invocation5XXErrors", "EndpointName", endpoint_name, "VariantName", "AllTraffic", { stat = "Sum", label = "${endpoint_name} 5XX" }]]
          )
          view    = "timeSeries"
          stacked = false
          region  = data.aws_region.current.name
          title   = "SageMaker Endpoints"
          period  = 300
        }
      },
      {
        type   = "log"
        width  = 24
        height = 6
        properties = {
          query  = "SOURCE '/aws/lambda/${var.lambda_function_name}' | fields @timestamp, @message | filter @message like /anomaly|remediation|jira|alert/ | sort @timestamp desc | limit 50"
          region = data.aws_region.current.name
          title  = "Recent Incident Flow Events"
          view   = "table"
        }
      }
    ]
  })
}

resource "aws_iam_role" "grafana" {
  count = var.enable_managed_grafana ? 1 : 0

  name = "${var.name_prefix}-grafana-workspace-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "grafana.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = var.common_tags
}

resource "aws_iam_role_policy_attachment" "grafana_cloudwatch_readonly" {
  count = var.enable_managed_grafana ? 1 : 0

  role       = aws_iam_role.grafana[0].name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchReadOnlyAccess"
}

resource "aws_grafana_workspace" "aiops" {
  count = var.enable_managed_grafana ? 1 : 0

  name                     = "${var.grafana_workspace_name}-${var.environment}"
  description              = "AIOps Grafana workspace for ${var.environment}"
  account_access_type      = "CURRENT_ACCOUNT"
  authentication_providers = ["AWS_SSO"]
  permission_type          = "SERVICE_MANAGED"
  role_arn                 = aws_iam_role.grafana[0].arn
  data_sources             = ["CLOUDWATCH"]
  notification_destinations = [
    "SNS"
  ]

  tags = var.common_tags

  depends_on = [
    aws_iam_role_policy_attachment.grafana_cloudwatch_readonly
  ]
}
