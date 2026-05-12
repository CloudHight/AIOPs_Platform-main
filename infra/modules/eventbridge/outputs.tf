output "module_name" {
  description = "Module identifier."
  value       = "eventbridge"
}

output "event_bus_name" {
  description = "AIOps event bus name."
  value       = aws_cloudwatch_event_bus.anomaly.name
}

output "event_bus_arn" {
  description = "AIOps event bus ARN."
  value       = aws_cloudwatch_event_bus.anomaly.arn
}

output "schedule_rule_arn" {
  description = "Scheduled detection rule ARN."
  value       = aws_cloudwatch_event_rule.scheduled_detection.arn
}
