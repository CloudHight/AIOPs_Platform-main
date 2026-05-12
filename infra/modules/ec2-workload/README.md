# ec2-workload

Terraform module for the monitored EC2 workload previously defined in `TERRAFORM_Code/`.

## Migrated Behavior

- Creates an IAM role and instance profile with CloudWatch Agent and SSM Session Manager permissions.
- Creates an HTTP-only security group. SSH is intentionally not opened.
- Looks up Amazon Linux 2 dynamically.
- Creates Nginx access and error log groups with configurable retention.
- Launches one EC2 instance tagged for anomaly monitoring.
- Bootstraps Docker, Nginx, the application container, CloudWatch Agent, and `stress-ng`.

## Security Notes

- No EC2 key pair is created.
- No private key is generated or written to Terraform state.
- No registry credentials are embedded in user data.
- Administrative access should use SSM Session Manager.

For private images, prefer ECR and IAM-based authentication.
