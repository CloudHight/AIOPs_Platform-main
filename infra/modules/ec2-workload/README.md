# ec2-workload

Terraform module for the monitored EC2 workload previously defined in `TERRAFORM_Code/`.

## Migrated Behavior

- Creates an IAM role and instance profile with CloudWatch Agent and SSM Session Manager permissions.
- Creates an HTTP-only security group. SSH is intentionally not opened.
- Optionally creates a temporary public HTTP-only ALB for stage/demo validation.
- Looks up Amazon Linux 2 dynamically.
- Creates Nginx access and error log groups with configurable retention.
- Launches one EC2 instance tagged for anomaly monitoring.
- Selects a subnet from AZs where the requested EC2 instance type is offered, unless an explicit subnet is provided.
- Bootstraps Docker, Nginx, the application container, CloudWatch Agent, and `stress-ng`.

## Security Notes

- No EC2 key pair is created.
- No private key is generated or written to Terraform state.
- No registry credentials are embedded in user data.
- Administrative access should use SSM Session Manager.
- `enable_public_http_alb` is intended for temporary stage/demo access only. Production should keep it disabled and use an HTTPS ALB/WAF design.

For private images, prefer ECR and IAM-based authentication.
