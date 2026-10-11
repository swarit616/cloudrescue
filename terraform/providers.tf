# Credentials are never configured here. They come from the standard AWS credential chain
# (SSO profile, environment, or an assumed role) when you run plan/apply in a later phase.
provider "aws" {
  region = var.aws_region

  default_tags {
    tags = local.tags
  }
}
