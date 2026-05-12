# TERRAFORM_Code

This folder contains a small Terraform setup that provisions one EC2-based application host in AWS and bootstraps it with Docker, Nginx, CloudWatch Agent, and a sample containerized app.

## Files in this folder

### `main.tf`

This is the main Terraform infrastructure definition.

It does the following:

- configures the AWS provider for `us-east-1` using the `default` CLI profile
- creates an IAM role for the EC2 instance
- attaches:
- `CloudWatchAgentServerPolicy`
- `AmazonSSMManagedInstanceCore`
- creates an IAM instance profile for the EC2 host
- looks up the default VPC and its subnets
- creates a security group that allows:
- SSH on port `22`
- HTTP on port `80`
- outbound traffic to anywhere
- looks up the latest Amazon Linux 2 AMI
- generates an RSA key pair locally with Terraform
- writes the private key to `ai-app-key.pem`
- creates an AWS EC2 key pair from the generated public key
- launches one EC2 instance with:
- instance type `t2.medium`
- public IP enabled
- the generated key pair
- the security group
- the IAM instance profile
- `AnomalyMonitoring = "enabled"` tag
- exposes two Terraform outputs:
- the instance public IP
- the instance ID

In practical terms, `main.tf` is the file that creates the machine and the AWS permissions needed for monitoring and management.

### `userdata.sh`

This is the EC2 instance bootstrap script executed through Terraform `user_data`.

It prepares the instance after launch by:

- updating system packages
- installing and enabling Docker
- installing and enabling Nginx
- configuring Nginx as a reverse proxy on port `80` to a container on port `8080`
- logging into a Docker registry
- pulling and running `cloudhight/testapp:latest`
- installing Amazon CloudWatch Agent
- configuring CloudWatch Agent to collect:
- CPU metrics
- nginx access logs
- nginx error logs
- starting the CloudWatch Agent
- installing `stress-ng` for optional CPU load simulation

It also contains commented-out traffic-generation and CPU-stress commands that can be used for testing.

In practical terms, this script turns a plain Amazon Linux instance into:

- a web server
- a container host
- a monitored node that sends metrics and logs to CloudWatch

## How the two files work together

The intended flow is:

1. Terraform creates the IAM role, networking, key pair, and EC2 instance in `main.tf`.
2. The EC2 instance runs the bootstrap commands in `userdata.sh`.
3. The app becomes reachable over HTTP through Nginx.
4. CPU metrics and nginx logs are shipped to CloudWatch for later anomaly detection and monitoring.

## Summary

This folder provisions one monitored EC2 application server. `main.tf` creates the AWS infrastructure, and `userdata.sh` configures the instance to run the app, expose it through Nginx, and publish logs and metrics to CloudWatch. 
