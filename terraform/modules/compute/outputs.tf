output "instance_id" {
  description = "EC2 instance id."
  value       = aws_instance.app.id
}

output "security_group_id" {
  description = "Application security group id."
  value       = aws_security_group.app.id
}
