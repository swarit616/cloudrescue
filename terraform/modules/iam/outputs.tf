output "role_name" {
  description = "Instance role name."
  value       = aws_iam_role.instance.name
}

output "instance_profile_name" {
  description = "Instance profile name."
  value       = aws_iam_instance_profile.instance.name
}
