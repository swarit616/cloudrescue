variable "name" {
  description = "Name prefix."
  type        = string
}

variable "environment" {
  description = "Environment name passed to the container."
  type        = string
}

variable "region" {
  description = "AWS region (used for the awslogs driver)."
  type        = string
}

variable "vpc_id" {
  description = "VPC id for the security group."
  type        = string
}

variable "subnet_id" {
  description = "Subnet to launch the instance in."
  type        = string
}

variable "instance_profile_name" {
  description = "IAM instance profile name."
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type."
  type        = string
}

variable "root_volume_size_gb" {
  description = "Root volume size in GiB."
  type        = number
}

variable "app_port" {
  description = "Published port."
  type        = number
}

variable "allowed_app_cidrs" {
  description = "CIDRs allowed to reach the app port."
  type        = list(string)
  default     = []
}

variable "container_image" {
  description = "Container image to run; empty = only install Docker."
  type        = string
  default     = ""
}

variable "log_group_name" {
  description = "CloudWatch log group the container logs to."
  type        = string
}
