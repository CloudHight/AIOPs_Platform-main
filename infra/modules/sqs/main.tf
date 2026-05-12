resource "aws_sqs_queue" "dlq" {
  name                      = "${var.name_prefix}-anomaly-dlq-${var.environment}"
  message_retention_seconds = 1209600
  kms_master_key_id         = var.kms_key_arn

  tags = merge(var.common_tags, {
    Type = "DLQ"
  })
}

resource "aws_sqs_queue" "processing" {
  name                       = "${var.name_prefix}-anomaly-processing-${var.environment}"
  visibility_timeout_seconds = var.visibility_timeout_seconds
  message_retention_seconds  = 1209600
  kms_master_key_id          = var.kms_key_arn

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = 3
  })

  tags = var.common_tags
}
