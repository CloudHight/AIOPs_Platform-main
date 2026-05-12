output "module_name" {
  description = "Module identifier."
  value       = "sns"
}

output "topic_arn" {
  description = "SNS notification topic ARN."
  value       = aws_sns_topic.notifications.arn
}

output "topic_name" {
  description = "SNS notification topic name."
  value       = aws_sns_topic.notifications.name
}
