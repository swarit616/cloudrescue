locals {
  name = "${var.project}-${var.environment}"

  tags = merge(
    {
      Project     = var.project
      Environment = var.environment
      ManagedBy   = "terraform"
    },
    var.extra_tags
  )
}

data "aws_availability_zones" "available" {
  state = "available"
}

module "network" {
  source = "./modules/network"

  name                 = local.name
  vpc_cidr             = var.vpc_cidr
  public_subnet_cidrs  = var.public_subnet_cidrs
  private_subnet_cidrs = var.private_subnet_cidrs
  availability_zones   = data.aws_availability_zones.available.names
}

module "monitoring" {
  source = "./modules/monitoring"

  name                = local.name
  log_retention_days  = var.log_retention_days
  enable_alarms       = var.enable_compute
  instance_id         = try(module.compute[0].instance_id, "")
  alarm_actions       = var.alarm_actions
  cpu_alarm_threshold = var.cpu_alarm_threshold
}

module "iam" {
  source = "./modules/iam"

  name          = local.name
  log_group_arn = module.monitoring.log_group_arn
}

module "compute" {
  source = "./modules/compute"
  count  = var.enable_compute ? 1 : 0

  name                  = local.name
  environment           = var.environment
  region                = var.aws_region
  vpc_id                = module.network.vpc_id
  subnet_id             = module.network.public_subnet_ids[0]
  instance_profile_name = module.iam.instance_profile_name
  instance_type         = var.instance_type
  root_volume_size_gb   = var.root_volume_size_gb
  app_port              = var.app_port
  allowed_app_cidrs     = var.allowed_app_cidrs
  container_image       = var.container_image
  log_group_name        = module.monitoring.log_group_name
}
