provider "aws" {
  region  = "us-east-1" # Change to your preferred region
  profile = "default"
}

# --- IAM Role and Instance Profile for CloudWatch Agent ---
resource "aws_iam_role" "cloudwatch_role" {
  name = "ec2-cloudwatch-agent-role1"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "cloudwatch_agent_attach" {
  role       = aws_iam_role.cloudwatch_role.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

resource "aws_iam_instance_profile" "cloudwatch_instance_profile" {
  name = "cloudwatch-agent-instance-profile1"
  role = aws_iam_role.cloudwatch_role.name
}

resource "aws_iam_role_policy_attachment" "ssm_attach" {
  role       = aws_iam_role.cloudwatch_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# --- Security Group allowing HTTP only; access is through SSM Session Manager ---
resource "aws_security_group" "app_sg" {
  name        = "ai-app-sg"
  description = "Allow HTTP; use SSM Session Manager for administration"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "Allow HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# Get default VPC & subnet
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# --- EC2 Instance ---
resource "aws_instance" "app_instance" {
  ami                         = data.aws_ami.amazon_linux.id
  instance_type               = "t2.medium"
  subnet_id                   = element(data.aws_subnets.default.ids, 0)
  vpc_security_group_ids      = [aws_security_group.app_sg.id]
  iam_instance_profile        = aws_iam_instance_profile.cloudwatch_instance_profile.name
  associate_public_ip_address = true
  user_data                   = file("${path.module}/userdata.sh")
  credit_specification {
    cpu_credits = "unlimited"
  }
  tags = {
    Name              = "ai-app-instance"
    Project           = "AIOPs"
    AnomalyMonitoring = "enabled"
  }
}

# Get latest Amazon Linux 2 AMI
data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
  }
}

# print the IP
output "ip" {
  value = aws_instance.app_instance.public_ip
}

# print the IP
output "id" {
  value = aws_instance.app_instance.id
}
