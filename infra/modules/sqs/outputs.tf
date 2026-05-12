output "module_name" {
  description = "Module identifier."
  value       = "sqs"
}

output "queue_url" {
  description = "Remediation queue URL."
  value       = aws_sqs_queue.processing.url
}

output "queue_arn" {
  description = "Remediation queue ARN."
  value       = aws_sqs_queue.processing.arn
}

output "queue_name" {
  description = "Remediation queue name."
  value       = aws_sqs_queue.processing.name
}

output "dlq_url" {
  description = "Remediation DLQ URL."
  value       = aws_sqs_queue.dlq.url
}

output "dlq_arn" {
  description = "Remediation DLQ ARN."
  value       = aws_sqs_queue.dlq.arn
}

output "dlq_name" {
  description = "Remediation DLQ name."
  value       = aws_sqs_queue.dlq.name
}
