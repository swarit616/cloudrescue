variable "name" {
  description = "Name prefix."
  type        = string
}

variable "log_group_arn" {
  description = "ARN of the CloudWatch log group the instance may write to."
  type        = string
}

variable "permissions_boundary_arn" {
  description = "ARN of the permissions boundary applied to the EC2 instance role."
  type        = string
}
