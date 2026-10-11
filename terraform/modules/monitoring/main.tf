resource "aws_cloudwatch_log_group" "app" {
  name              = "/${var.name}/app"
  retention_in_days = var.log_retention_days
}

# Alarms are created only when an instance exists (enable_alarms is a plain bool so the
# count is known at plan time even though the instance id is not).
resource "aws_cloudwatch_metric_alarm" "cpu_high" {
  count = var.enable_alarms ? 1 : 0

  alarm_name          = "${var.name}-cpu-high"
  alarm_description   = "Average EC2 CPU above ${var.cpu_alarm_threshold}% for 10 minutes"
  namespace           = "AWS/EC2"
  metric_name         = "CPUUtilization"
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 2
  threshold           = var.cpu_alarm_threshold
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "missing"
  alarm_actions       = var.alarm_actions
  ok_actions          = var.alarm_actions
  dimensions          = { InstanceId = var.instance_id }
}

resource "aws_cloudwatch_metric_alarm" "status_check_failed" {
  count = var.enable_alarms ? 1 : 0

  alarm_name          = "${var.name}-status-check-failed"
  alarm_description   = "EC2 instance or system status check failing"
  namespace           = "AWS/EC2"
  metric_name         = "StatusCheckFailed"
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 2
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "breaching"
  alarm_actions       = var.alarm_actions
  ok_actions          = var.alarm_actions
  dimensions          = { InstanceId = var.instance_id }
}
