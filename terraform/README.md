# Terraform foundation (future AWS deployment)

> **Status: written and syntax-checked locally only. Nothing has been planned against AWS, nothing has been applied,
> and no AWS resources exist.** The `apply` command is intentionally never used by any script, Makefile target or CI job.

## Layout

```
terraform/
├── versions.tf        # Terraform >= 1.5, AWS provider ~> 5.0
├── providers.tf       # provider + default tags (no credentials)
├── main.tf            # wires the modules together
├── variables.tf       # inputs with validation
├── outputs.tf
├── backend.tf.example # remote state template (inactive)
├── environments/
│   ├── dev.tfvars     # environment-specific values live here...
│   └── prod.tfvars    # ...never inside modules (placeholder sizing)
└── modules/
    ├── network/       # VPC, public + private subnets, IGW, route tables, locked-down default SG
    ├── iam/           # EC2 role: SSM Session Manager + write-only access to ITS OWN log group
    ├── compute/       # security group (no inbound by default) + one small EC2 instance running Docker
    └── monitoring/    # CloudWatch log group + CPU and status-check alarms
```

Every module contains real resources. Anything not built yet is listed under "Deferred" instead of being a stub module.

## What each environment would create

| Resource | Cost note (indicative, us-east-1; check the AWS pricing pages) |
|---|---|
| VPC, subnets, route tables, internet gateway, default SG | Free |
| IAM role, instance profile, policies | Free |
| CloudWatch log group | Pay for ingestion/storage; negligible for a demo |
| EC2 `t3.micro` + 8 GiB encrypted gp3 + public IPv4 | Only when `enable_compute = true`; a few USD/month if left running |
| CloudWatch alarms (2) | Only with compute; roughly USD 0.10/alarm/month |

`enable_compute` defaults to **false**, so the default plan contains only free/near-free resources.

## Security defaults

* No SSH. Use SSM Session Manager (role includes `AmazonSSMManagedInstanceCore`).
* Security group has **no inbound rules** unless `allowed_app_cidrs` is set; `0.0.0.0/0` is rejected by validation.
* IMDSv2 required, encrypted root volume, default VPC security group locked down.
* The instance role can write only to its own log group.
* The container is started with `CLOUDRESCUE_DEMO_ENDPOINTS_ENABLED=false`.
* No credentials, account ids or keys in any file.

## Checks you can run locally (no AWS account needed)

```bash
terraform -chdir=terraform fmt -check -recursive       # formatting
terraform -chdir=terraform init -backend=false         # downloads the AWS provider plugin (needs internet, not AWS credentials)
terraform -chdir=terraform validate                    # syntax and internal consistency
# or:
make tf-validate
```

`terraform init` contacts the Terraform registry to download the provider; this is the only network access and it needs no
credentials. `terraform fmt` and `terraform validate` do not contact AWS.

## Later phase only (needs AWS credentials; do not run yet)

```bash
terraform -chdir=terraform plan -var-file=environments/dev.tfvars    # read-only preview
```

`plan` reads data sources (availability zones, AMI) from AWS, so it requires credentials. Review the plan and
`docs/aws-deployment-plan.md` before any `apply`.

## Deferred (intentionally not implemented)

* Application Load Balancer and Auto Scaling group (cost; needs health-check design and TLS certificates)
* NAT gateway for private subnets (about USD 32/month plus data processing)
* ECR repository and image publishing pipeline (`container_image` is empty by default)
* SNS topic and notification wiring for alarms (`alarm_actions` accepts ARNs)
* GitHub OIDC deployment role, remote state bucket and lock table
* VPC flow logs, CloudWatch agent / container metrics, WAF
