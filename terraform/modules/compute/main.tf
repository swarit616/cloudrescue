data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_security_group" "app" {
  name_prefix = "${var.name}-app-"
  description = "CloudRescue app: no inbound unless allowed_app_cidrs is set"
  vpc_id      = var.vpc_id
  tags        = { Name = "${var.name}-app-sg" }

  dynamic "ingress" {
    for_each = var.allowed_app_cidrs

    content {
      description = "App port from an explicitly allowed CIDR"
      from_port   = var.app_port
      to_port     = var.app_port
      protocol    = "tcp"
      cidr_blocks = [ingress.value]
    }
  }

  egress {
    description = "Outbound (package install, image pull, SSM, CloudWatch)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_instance" "app" {
  ami                         = data.aws_ami.al2023.id
  instance_type               = var.instance_type
  subnet_id                   = var.subnet_id
  vpc_security_group_ids      = [aws_security_group.app.id]
  iam_instance_profile        = var.instance_profile_name
  associate_public_ip_address = true
  monitoring                  = false
  user_data_replace_on_change = true
  tags                        = { Name = "${var.name}-app" }

  user_data = templatefile("${path.module}/templates/user_data.sh.tftpl", {
    app_port        = var.app_port
    environment     = var.environment
    region          = var.region
    log_group_name  = var.log_group_name
    container_image = var.container_image
  })

  metadata_options {
    http_endpoint = "enabled"
    http_tokens   = "required"
  }

  root_block_device {
    volume_type = "gp3"
    volume_size = var.root_volume_size_gb
    encrypted   = true
  }
}
