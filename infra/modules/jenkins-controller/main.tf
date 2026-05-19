data "aws_vpc" "default" {
  count   = var.vpc_id == null ? 1 : 0
  default = true
}

data "aws_ec2_instance_type_offerings" "jenkins" {
  count         = var.subnet_id == null ? 1 : 0
  location_type = "availability-zone"

  filter {
    name   = "instance-type"
    values = [var.instance_type]
  }
}

data "aws_subnets" "selected" {
  count = var.subnet_id == null ? 1 : 0

  filter {
    name   = "vpc-id"
    values = [local.vpc_id]
  }

  filter {
    name   = "availability-zone"
    values = local.jenkins_availability_zones
  }
}

data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-x86_64"]
  }
}

locals {
  resource_prefix = "${var.name_prefix}-${var.environment}-jenkins"
  vpc_id          = var.vpc_id != null ? var.vpc_id : data.aws_vpc.default[0].id
  jenkins_availability_zones = (
    var.subnet_id != null
    ? []
    : sort(data.aws_ec2_instance_type_offerings.jenkins[0].locations)
  )
  subnet_id = var.subnet_id != null ? var.subnet_id : sort(data.aws_subnets.selected[0].ids)[0]

  artifact_object_arns = flatten([
    for bucket_arn in var.artifact_bucket_arns : [
      bucket_arn,
      "${bucket_arn}/*"
    ]
  ])
}

#checkov:skip=CKV_AWS_260: User requested public Jenkins UI access from anywhere for this demo controller.
#tfsec:ignore:aws-ec2-no-public-ingress-sgr User requested public Jenkins UI access from anywhere for this demo controller.
resource "aws_security_group" "jenkins" {
  name        = "${local.resource_prefix}-sg"
  description = "Jenkins controller access; administration should use SSM Session Manager"
  vpc_id      = local.vpc_id

  dynamic "ingress" {
    for_each = toset(var.allowed_jenkins_cidrs)

    content {
      description = "Jenkins HTTP UI"
      from_port   = 8080
      to_port     = 8080
      protocol    = "tcp"
      cidr_blocks = [ingress.value]
    }
  }

  egress {
    description = "Outbound package, AWS API, and plugin access"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.common_tags, {
    Name = "${local.resource_prefix}-sg"
  })
}

resource "aws_iam_role" "jenkins" {
  name = "${local.resource_prefix}-role"

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

resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.jenkins.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy_attachment" "cloudwatch_agent" {
  role       = aws_iam_role.jenkins.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

resource "aws_iam_role_policy" "assume_deploy_roles" {
  count = length(var.allowed_deploy_role_arns) > 0 ? 1 : 0

  name = "${local.resource_prefix}-assume-deploy-roles"
  role = aws_iam_role.jenkins.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "sts:AssumeRole"
        Resource = var.allowed_deploy_role_arns
      }
    ]
  })
}

resource "aws_iam_role_policy" "artifact_buckets" {
  count = length(var.artifact_bucket_arns) > 0 ? 1 : 0

  name = "${local.resource_prefix}-artifact-buckets"
  role = aws_iam_role.jenkins.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
          "s3:GetBucketLocation"
        ]
        Resource = local.artifact_object_arns
      }
    ]
  })
}

resource "aws_iam_instance_profile" "jenkins" {
  name = "${local.resource_prefix}-profile"
  role = aws_iam_role.jenkins.name

  tags = var.common_tags
}

resource "aws_instance" "jenkins" {
  ami                         = data.aws_ami.amazon_linux_2023.id
  instance_type               = var.instance_type
  subnet_id                   = local.subnet_id
  vpc_security_group_ids      = [aws_security_group.jenkins.id]
  iam_instance_profile        = aws_iam_instance_profile.jenkins.name
  associate_public_ip_address = var.associate_public_ip_address
  user_data_replace_on_change = true
  user_data = templatefile("${path.module}/templates/userdata.sh.tftpl", {
    jenkins_home_device_name = var.jenkins_home_device_name
  })

  root_block_device {
    volume_size = var.root_volume_size_gb
    volume_type = "gp3"
    encrypted   = true
  }

  ebs_block_device {
    device_name           = var.jenkins_home_device_name
    volume_size           = var.jenkins_home_volume_size_gb
    volume_type           = "gp3"
    encrypted             = true
    delete_on_termination = false
  }

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }

  tags = merge(var.common_tags, {
    Name    = "${local.resource_prefix}-controller"
    Project = "AIOPs"
    Role    = "JenkinsController"
  })

  depends_on = [
    aws_iam_role_policy_attachment.ssm,
    aws_iam_role_policy_attachment.cloudwatch_agent
  ]
}
