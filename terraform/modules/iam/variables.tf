variable "name" {
  description = "Name prefix."
  type        = string
}

variable "log_group_arn" {
  description = "ARN of the CloudWatch log group the instance may write to."
  type        = string
}
