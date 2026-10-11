output "vpc_id" {
  description = "VPC id."
  value       = module.network.vpc_id
}

output "public_subnet_ids" {
  description = "Public subnet ids."
  value       = module.network.public_subnet_ids
}

output "private_subnet_ids" {
  description = "Private subnet ids."
  value       = module.network.private_subnet_ids
}

output "log_group_name" {
  description = "CloudWatch log group for the application."
  value       = module.monitoring.log_group_name
}

output "instance_id" {
  description = "EC2 instance id (null when enable_compute = false)."
  value       = one(module.compute[*].instance_id)
}

output "instance_role_name" {
  description = "IAM role attached to the instance."
  value       = module.iam.role_name
}
