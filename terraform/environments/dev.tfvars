# Environment-specific values live here, never inside modules.
# Use with: terraform plan -var-file=environments/dev.tfvars   (needs AWS credentials; do NOT apply yet)
environment          = "dev"
aws_region           = "us-east-1"
vpc_cidr             = "10.40.0.0/16"
public_subnet_cidrs  = ["10.40.1.0/24"]
private_subnet_cidrs = ["10.40.101.0/24"]
enable_compute       = false
instance_type        = "t3.micro"
log_retention_days   = 7
