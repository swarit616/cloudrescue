variable "aws_region" {
  description = "AWS region for the deployment."
  type        = string
  default     = "us-east-1"
}

variable "project" {
  description = "Project name used as a prefix for resource names."
  type        = string
  default     = "cloudrescue"
}

variable "environment" {
  description = "Environment name. Set per environment via environments/<name>.tfvars."
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod."
  }
}

variable "vpc_cidr" {
  description = "CIDR block of the VPC."
  type        = string
  default     = "10.40.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks of the public subnets (one per availability zone used)."
  type        = list(string)
  default     = ["10.40.1.0/24"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks of the private subnets (no NAT gateway yet; see README)."
  type        = list(string)
  default     = ["10.40.101.0/24"]
}

variable "enable_compute" {
  description = "Create the EC2 instance and its CloudWatch alarms. false (default) keeps the plan free of compute cost."
  type        = bool
  default     = false
}

variable "instance_type" {
  description = "EC2 instance type (kept small to limit cost)."
  type        = string
  default     = "t3.micro"
}

variable "root_volume_size_gb" {
  description = "Root EBS volume size in GiB."
  type        = number
  default     = 8
}

variable "app_port" {
  description = "Host port the container is published on."
  type        = number
  default     = 8000
}

variable "allowed_app_cidrs" {
  description = "CIDR blocks allowed to reach the app port. Empty (default) = no inbound access."
  type        = list(string)
  default     = []

  validation {
    condition     = alltrue([for cidr in var.allowed_app_cidrs : cidr != "0.0.0.0/0"])
    error_message = "Do not expose the demo endpoints to the whole internet (0.0.0.0/0)."
  }
}

variable "container_image" {
  description = "Container image to run on the instance. Empty = start Docker only (no ECR yet)."
  type        = string
  default     = ""
}

variable "log_retention_days" {
  description = "CloudWatch Logs retention in days."
  type        = number
  default     = 14
}

variable "alarm_actions" {
  description = "ARNs (for example an SNS topic) notified when an alarm fires. Empty = alarms only change state."
  type        = list(string)
  default     = []
}

variable "cpu_alarm_threshold" {
  description = "Average CPU percent that triggers the high-CPU alarm."
  type        = number
  default     = 80
}

variable "extra_tags" {
  description = "Additional tags applied to every resource."
  type        = map(string)
  default     = {}
}
