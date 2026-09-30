# PhotoVault: AWS Demo Architecture

A small photo-sharing app (upload, view, delete) built to show how core AWS services work together: networking, compute, load balancing, storage, CDN, identity, monitoring, auditing and alerting. It is designed to run for a day or two and then be destroyed.

The app is served at the default `https://<id>.cloudfront.net` URL. No custom domain or Route 53 is used.

## Architecture

```
                     Browser
                        |
                   CloudFront  (default *.cloudfront.net URL, HTTPS)
                  /            \
        /photos/* (cached)      everything else (not cached)
              |                        |
   S3 photos bucket (private,    Application Load Balancer
   access via OAC)               (2 public subnets, 2 AZs)
              ^                        |
              |                   EC2 x2 (Flask + gunicorn)
              +---- IAM role ----------+   SG allows port 80 only from the ALB
                    (PutObject/GetObject/DeleteObject on photos/* only)

  CloudTrail -> S3 (log bucket) + CloudWatch Logs -> metric filter -> alarm --+
  CloudWatch alarms (EC2 CPU, unhealthy ALB hosts) -------------------------+--> SNS -> Email
```

## Services used

| Service | Role |
|---|---|
| VPC, subnets, route table, Internet Gateway | 1 VPC, 2 public subnets in different AZs, `0.0.0.0/0` routed to the IGW |
| EC2 | Runs the Flask app (Amazon Linux 2023, installed via user data) |
| Application Load Balancer | Spreads traffic across the EC2 instances, health check on `/health` |
| S3 | Private photo bucket, plus a separate bucket for CloudTrail logs |
| CloudFront | Single entry point. Caches `/photos/*` from S3 (via Origin Access Control); passes everything else to the ALB uncached |
| IAM | EC2 instance role with least-privilege S3 access, plus SSM access for shell sessions |
| CloudWatch | Alarms for CPU and unhealthy hosts, a log group and metric filter for CloudTrail events |
| CloudTrail | Records API calls to S3 and CloudWatch Logs |
| SNS | Emails you when any alarm fires |

## Files

| File | Purpose |
|---|---|
| `main.tf` | All infrastructure |
| `app.py` | Flask app (upload, list, delete, `/health`) |
| `user_data.sh` | EC2 boot script: installs dependencies, writes `app.py`, starts it as a systemd service |

## Prerequisites

- An AWS account and credentials with permission to create the resources above. The easiest route is **AWS CloudShell**, where you only need to install Terraform.
- [Terraform](https://developer.hashicorp.com/terraform/install) 1.5 or newer.
- An email address you can check (for SNS alerts).

## Deploy

```bash
terraform init
terraform apply -var="alert_email=you@example.com"
```

Then:

1. **Confirm the SNS subscription** from the email AWS sends. Until you do, no alerts are delivered.
2. **Wait about 5-10 minutes.** CloudFront takes a few minutes to deploy and the EC2 instances need a couple of minutes to boot and pass health checks.
3. Open the `app_url` value printed at the end.

### Variables

| Variable | Default | Notes |
|---|---|---|
| `alert_email` | none (required) | Receives SNS alerts |
| `region` | `ap-south-1` | Any region works |
| `instance_type` | `t3.micro` | Must be free-tier eligible in your region and account. Look for the "Free tier eligible" tag in the EC2 launch wizard. It may be `t2.micro` |
| `instance_count` | `2` | Use `1` to save free-tier hours. The failover demo needs 2 |

Example: `terraform apply -var="alert_email=you@example.com" -var="instance_type=t2.micro" -var="instance_count=1"`

## Demo script (about 10 minutes)

1. **Upload photos.** The app uploads to S3 using its IAM role. The gallery loads images through CloudFront at `/photos/*`.
2. **CloudFront caching.** Open a photo in its own tab, then check the response headers in DevTools. The second load should show `x-cache: Hit from cloudfront`. Note that a deleted photo may keep showing for a while because it is cached.
3. **High availability.** Refresh the page and watch the instance ID in the footer change. Stop one EC2 instance from the console. The site keeps working, and the `photovault-unhealthy-hosts` alarm emails you.
4. **CloudWatch alarm.** Open a shell on an instance (EC2 console, Connect, Session Manager) and run:
   ```bash
   for i in 1 2; do (timeout 420 sh -c 'while :; do :; done' &); done
   ```
   The CPU alarm fires within about 5-10 minutes and SNS sends an email.
5. **CloudTrail audit and alert.** Add any inbound rule to a security group (for example TCP 8080 on the EC2 group). CloudTrail records the event, the metric filter matches it, and the `photovault-security-group-changed` alarm emails you after a few minutes. You can also show the raw event in the CloudTrail event history.
6. **IAM least privilege.** In the same Session Manager shell, compare:
   ```bash
   aws s3 ls s3://<photos_bucket>/photos/    # allowed
   aws s3 ls s3://<some-other-bucket>/       # AccessDenied
   ```
   The bucket name is in the `photos_bucket` output.

## Cost and free tier

The expected cost of running this for 1-2 days is around zero, and at worst a few dollars if nothing is covered by free tier or credits.

- **Legacy free tier** (accounts created before 15 July 2025): 750 hours each of EC2 and ALB per month for 12 months, plus a public IPv4 allowance. Two instances running 24/7 would exceed the EC2 hours, so use `instance_count=1` if you plan to run it longer than a couple of days.
- **Newer accounts:** usage is drawn from your credits instead. Check **Billing, Free Tier** to see which model applies to you.
- **Not covered by free tier:** ALB time after the allowance (~$16-20/month), public IPv4 addresses beyond the allowance (~$3.65/month each), and any custom domain or Route 53 hosted zone (not used here).
- **Always-free allowances** cover the rest at demo scale: CloudFront (1 TB and 10M requests per month), CloudWatch (10 alarms, 5 GB of logs), SNS email, IAM and VPC.
- **Avoid:** NAT Gateways, CloudTrail S3 data events and SMS alerts. This project uses none of them.
- `cpu_credits = "standard"` is set on the instances so the CPU stress test cannot run up "unlimited mode" charges.

Set a **$1 AWS Budgets alert** before deploying. Prices are approximate, so confirm current rates on the AWS pricing pages.

## Cleanup

```bash
terraform destroy -var="alert_email=you@example.com"
```

Both S3 buckets are set to `force_destroy`, so they are emptied automatically. CloudFront distributions take several minutes to delete. Afterwards, check the EC2, load balancer and CloudFront consoles for leftovers and review **Billing, Bills** the next day.

If you change resources by hand in the console (for example the security group in demo step 5), Terraform may report drift on the next run. Remove the extra rule manually or let `terraform apply` or `destroy` reconcile it.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `502` or `504` from CloudFront | Instances are still booting or not yet healthy. Wait a few minutes and check the target group in the EC2 console |
| Instance type error on apply | The type isn't available or eligible in your region or account. Try `t2.micro` or `t3.micro` |
| No alert emails | The SNS subscription was not confirmed, or the alert is still pending (CloudTrail to alarm takes several minutes) |
| Photos don't appear | Check the app logs via Session Manager with `sudo journalctl -u photovault`. Confirm the IAM role is attached to the instance |
| Deleted photo still visible | CloudFront is serving the cached copy. It expires on its own |

## Security notes (demo-grade)

- The ALB accepts HTTP from anywhere, and CloudFront connects to it over plain HTTP because there is no custom domain certificate. Fine for a short demo, not for production.
- Instances sit in public subnets to avoid the cost of a NAT Gateway. Their security group only allows traffic from the ALB, and there is no SSH (use Session Manager).
- In production you would use private subnets, HTTPS end to end with an ACM certificate, a WAF, and restrict the ALB to CloudFront's IP ranges.
