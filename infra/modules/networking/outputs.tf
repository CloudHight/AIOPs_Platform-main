output "module_name" {
  description = "Module identifier."
  value       = "networking"
}

output "vpc_id" {
  description = "VPC ID after migration."
  value       = null
}

output "private_subnet_ids" {
  description = "Private subnet IDs after migration."
  value       = []
}

