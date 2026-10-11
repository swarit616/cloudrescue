# AWS deployment plan (future phase)

> **Nothing in this document has been done.** No AWS account, role, resource or pipeline has been touched.
> It describes the intended sequence so that the local foundation can be connected safely later.

## Prerequisites

* An AWS account you own, with MFA on the root user and a budget alert (for example USD 5) configured **first**.
* An SSO/IAM Identity Center user or a dedicated admin role for humans; no long-lived access keys.
* Local checks green: `make test`, `make lint`, `make tf-validate`.

## Sequence

1. **Budget and guardrails** - AWS Budgets alert, billing alarm, region restriction (optional SCP).
2. **Remote state** - create a versioned, encrypted S3 bucket and a DynamoDB lock table (or use S3 native locking where
   available). Copy `terraform/backend.tf.example` to `backend.tf` and run `terraform init -backend-config="key=cloudrescue/dev/terraform.tfstate"`.
3. **Plan only** - `terraform -chdir=terraform plan -var-file=environments/dev.tfvars` with `enable_compute = false`. Review
   every resource. This costs nothing.
4. **Apply network + IAM + logging** (free tier of resources) after review.
5. **Image publishing** - add an ECR repository (new module), build and push the container from CI, then set `container_image`.
6. **Enable compute** - set `enable_compute = true`, plan, review cost, apply. Connect with SSM Session Manager, not SSH.
7. **Verify** - container logs in CloudWatch, alarms in `OK`, `GET /health` through an allowed CIDR (or SSM port forwarding).
8. **Add the real integration** (code change): read-only AWS calls first (`ec2:DescribeInstanceStatus`,
   CloudWatch `GetMetricData`), reported in the `aws` section of `/api/status`, never mixed with the simulation.
9. **Only then** consider ALB + Auto Scaling (TLS certificate, health checks, WAF) for public hosting.

## CI/CD with GitHub OIDC (no stored keys)

1. Create an IAM OIDC identity provider for `token.actions.githubusercontent.com`.
2. Create two roles trusted only by this repository:
   * `cloudrescue-plan` - read-only, assumable from pull requests (`repo:<owner>/cloudrescue:pull_request`)
   * `cloudrescue-apply` - write access to only the resources in this project, assumable only from `refs/heads/main`
     through a protected GitHub Environment that requires manual approval.
3. In workflows: `permissions: { id-token: write, contents: read }` and `aws-actions/configure-aws-credentials` with `role-to-assume`.
4. The current CI deliberately has no AWS access; add the plan job only after step 2 exists.

## Security checklist (before anything is public)

- [ ] Demo endpoints disabled (`CLOUDRESCUE_DEMO_ENDPOINTS_ENABLED=false`) or protected by a token **and** network controls
- [ ] No inbound rule from `0.0.0.0/0` except an ALB listener on 443 with TLS
- [ ] No SSH; SSM Session Manager only
- [ ] IMDSv2 required, encrypted volumes, least-privilege instance role (already in the modules)
- [ ] State bucket private, versioned, encrypted; state never committed
- [ ] Image scanned in CI (ECR scan / Trivy) and pinned by digest
- [ ] CloudTrail enabled; alarms routed to a real notification channel
- [ ] Rate limiting / WAF in front of any public endpoint
- [ ] Secrets in SSM Parameter Store or Secrets Manager, never in user data or tfvars

## Cost considerations

| Item | Approximate cost (verify on the AWS pricing pages) |
|---|---|
| `t3.micro` EC2 | Free-tier eligible for new accounts (limits apply); otherwise roughly USD 8/month |
| Public IPv4 address | About USD 3.60/month per address |
| EBS 8 GiB gp3 | Under USD 1/month |
| NAT gateway (deferred) | About USD 32/month plus data processing - the most common surprise |
| Application Load Balancer (deferred) | About USD 16-20/month minimum |
| CloudWatch logs/alarms | Small for a demo; ingestion is billed per GB |

Forgotten resources are the main risk: set a budget alert, tag everything (done via `default_tags`), and tear down after demos.

## Teardown

```bash
terraform -chdir=terraform plan -destroy -var-file=environments/dev.tfvars   # review what will be removed
terraform -chdir=terraform destroy -var-file=environments/dev.tfvars         # only after review
```

Afterwards: confirm in the console that no EC2 instances, volumes, Elastic IPs, NAT gateways or load balancers remain, delete
the state bucket/lock table if the project is retired, and check the next day's billing page.
