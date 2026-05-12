resource "aws_cloudwatch_event_bus" "anomaly" {
  name = "${var.name_prefix}-anomaly-events-${var.environment}"

  tags = var.common_tags
}

resource "aws_cloudwatch_event_rule" "scheduled_detection" {
  name                = "${var.name_prefix}-anomaly-detection-schedule-${var.environment}"
  description         = "Scheduled execution for anomaly detection"
  schedule_expression = var.monitoring_frequency

  tags = var.common_tags
}

resource "aws_cloudwatch_event_target" "scheduled_lambda" {
  rule      = aws_cloudwatch_event_rule.scheduled_detection.name
  target_id = "AnomalyDetectionLambda"
  arn       = var.lambda_function_arn
}

resource "aws_lambda_permission" "allow_eventbridge_schedule" {
  statement_id  = "AllowExecutionFromEventBridgeSchedule"
  action        = "lambda:InvokeFunction"
  function_name = var.lambda_function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.scheduled_detection.arn
}

resource "aws_cloudwatch_event_rule" "anomaly_events" {
  name           = "${var.name_prefix}-anomaly-event-rule-${var.environment}"
  description    = "Rule to capture anomaly detection events"
  event_bus_name = aws_cloudwatch_event_bus.anomaly.name

  event_pattern = jsonencode({
    source = [
      "anomaly-detection.${var.environment}"
    ]
    "detail-type" = [
      "CPU Anomaly Detected",
      "Log Anomaly Detected"
    ]
    detail = {
      score = [
        {
          numeric = [">", 0.7]
        }
      ]
    }
  })

  tags = var.common_tags
}

resource "aws_cloudwatch_event_target" "anomaly_sns" {
  rule           = aws_cloudwatch_event_rule.anomaly_events.name
  event_bus_name = aws_cloudwatch_event_bus.anomaly.name
  target_id      = "SendToSNS"
  arn            = var.sns_topic_arn

  input_transformer {
    input_paths = {
      instanceId  = "$.detail.instance_id"
      anomalyType = "$.detail.anomaly_type"
      score       = "$.detail.score"
      jiraTicket  = "$.detail.jira_ticket_id"
    }

    input_template = jsonencode({
      default = "Anomaly Detected"
      email = {
        instance_id  = "<instanceId>"
        anomaly_type = "<anomalyType>"
        score        = "<score>"
        jira_ticket  = "<jiraTicket>"
      }
    })
  }
}

resource "aws_sns_topic_policy" "allow_eventbridge" {
  arn = var.sns_topic_arn

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowEventBridgePublish"
        Effect = "Allow"
        Principal = {
          Service = "events.amazonaws.com"
        }
        Action   = "sns:Publish"
        Resource = var.sns_topic_arn
        Condition = {
          ArnEquals = {
            "aws:SourceArn" = aws_cloudwatch_event_rule.anomaly_events.arn
          }
        }
      }
    ]
  })
}
