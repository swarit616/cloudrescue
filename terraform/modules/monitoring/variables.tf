variable "name" {
  description = "Name prefix."
  type        = string
}

variable "log_retention_days" {
  description = "CloudWatch Logs retention in days."
  type        = number
}

variable "enable_alarms" {
  description = "Create the EC2 alarms (set true only when an instance exists)."
  type        = bool
}

variable "instance_id" {
  description = "EC2 instance id the alarms watch."
  type        = string
  default     = ""
}

variable "alarm_actions" {
  description = "Notification ARNs for alarm state changes."
  type        = list(string)
  default     = []
}

variable "cpu_alarm_threshold" {
  description = "Average CPU percent threshold."
  type        = number
}
