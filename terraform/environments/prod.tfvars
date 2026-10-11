# PLACEHOLDER sizing for a future production environment. Review before ever using it.
# A real prod setup would add an ALB, Auto Scaling and NAT (all deferred; see terraform/README.md).
environment          = "prod"
aws_region           = "us-east-1"
vpc_cidr             = "10.50.0.0/16"
public_subnet_cidrs  = ["10.50.1.0/24", "10.50.2.0/24"]
private_subnet_cidrs = ["10.50.101.0/24", "10.50.102.0/24"]
enable_compute       = false
instance_type        = "t3.small"
log_retention_days   = 90
