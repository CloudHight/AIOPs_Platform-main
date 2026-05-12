data "aws_vpc" "default" {
  count   = var.vpc_id == null ? 1 : 0
  default = true
}

data "aws_subnets" "selected" {
  count = var.subnet_id == null ? 1 : 0

  filter {
    name   = "vpc-id"
    values = [local.vpc_id]
  }
}

data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["137112412989"]

  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
  }
}

locals {
  name_prefix = "${var.name_prefix}-${var.environment}"
  vpc_id      = var.vpc_id != null ? var.vpc_id : data.aws_vpc.default[0].id
  subnet_id   = var.subnet_id != null ? var.subnet_id : sort(data.aws_subnets.selected[0].ids)[0]

  workload_tags = merge(
    var.common_tags,
    {
      Name                     = "${local.name_prefix}-workload"
      Project                  = "AIOPs"
      (var.monitoring_tag_key) = var.monitoring_tag_value
    }
  )
}

resource "aws_cloudwatch_log_group" "nginx_access" {
  name              = var.nginx_access_log_group_name
  retention_in_days = var.log_retention_days
  kms_key_id        = var.cloudwatch_log_kms_key_id
}

resource "aws_cloudwatch_log_group" "nginx_error" {
  name              = var.nginx_error_log_group_name
  retention_in_days = var.log_retention_days
  kms_key_id        = var.cloudwatch_log_kms_key_id
}

resource "aws_iam_role" "workload" {
  name = "${local.name_prefix}-ec2-workload-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = var.common_tags
}

resource "aws_iam_role_policy_attachment" "cloudwatch_agent" {
  role       = aws_iam_role.workload.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.workload.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "workload" {
  name = "${local.name_prefix}-ec2-workload-profile"
  role = aws_iam_role.workload.name

  tags = var.common_tags
}

resource "aws_security_group" "workload" {
  name        = "${local.name_prefix}-workload-sg"
  description = "Allow HTTP to the AIOps workload; administration uses SSM Session Manager"
  vpc_id      = local.vpc_id

  dynamic "ingress" {
    for_each = toset(var.allowed_http_cidrs)

    content {
      description = "HTTP"
      from_port   = 80
      to_port     = 80
      protocol    = "tcp"
      cidr_blocks = [ingress.value]
    }
  }

  egress {
    description = "Outbound HTTPS for SSM, CloudWatch, ECR, package install, and image pull"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.common_tags, {
    Name = "${local.name_prefix}-workload-sg"
  })
}

resource "aws_instance" "workload" {
  #checkov:skip=CKV_AWS_46: User data contains bootstrap configuration only; credentials are not embedded and access uses IAM/SSM.
  ami                         = data.aws_ami.amazon_linux.id
  instance_type               = var.instance_type
  subnet_id                   = local.subnet_id
  vpc_security_group_ids      = [aws_security_group.workload.id]
  iam_instance_profile        = aws_iam_instance_profile.workload.name
  associate_public_ip_address = var.associate_public_ip_address
  monitoring                  = true
  ebs_optimized               = var.ebs_optimized
  user_data_replace_on_change = true
  user_data = templatefile("${path.module}/templates/userdata.sh.tftpl", {
    app_image                   = var.app_image
    nginx_access_log_group_name = var.nginx_access_log_group_name
    nginx_error_log_group_name  = var.nginx_error_log_group_name
  })

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  root_block_device {
    encrypted = true
  }

  credit_specification {
    cpu_credits = "unlimited"
  }

  tags = local.workload_tags

  depends_on = [
    aws_cloudwatch_log_group.nginx_access,
    aws_cloudwatch_log_group.nginx_error,
    aws_iam_role_policy_attachment.cloudwatch_agent,
    aws_iam_role_policy_attachment.ssm,
  ]
}
