resource "aws_sns_topic" "notifications" {
  name              = "${var.name_prefix}-anomaly-notifications-${var.environment}"
  display_name      = "Anomaly Detection Notifications - ${var.environment}"
  kms_master_key_id = var.kms_key_arn

  tags = var.common_tags
}

resource "aws_sns_topic_subscription" "email" {
  count = var.notification_email == null ? 0 : 1

  topic_arn = aws_sns_topic.notifications.arn
  protocol  = "email"
  endpoint  = var.notification_email
}
