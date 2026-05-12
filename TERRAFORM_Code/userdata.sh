#!/bin/bash
set -e

# Update system
yum update -y

# Install Docker
amazon-linux-extras enable docker
yum install -y docker
systemctl enable docker
systemctl start docker
usermod -aG docker ec2-user

# Install Nginx
amazon-linux-extras enable nginx1
yum install -y nginx
systemctl enable nginx
systemctl start nginx

# Configure Nginx to listen on localhost:8080 and proxy requests to Docker container
cat <<EOF > /etc/nginx/conf.d/app.conf
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }
}
EOF

# Test and restart Nginx
nginx -t && systemctl restart nginx

# Pull and run the application container.
# Use a public image for the current demo path. For private images, prefer ECR
# with instance-profile IAM auth instead of embedding registry credentials here.
APP_IMAGE="${APP_IMAGE:-cloudhight/testapp:latest}"
docker pull "${APP_IMAGE}"
docker run -d -p 8080:8080 --name cloudhight-app --restart=unless-stopped "${APP_IMAGE}"

# generate some traffic to create logs
# for i in {1..1000}; do curl -s http://localhost/ > /dev/null; sleep 0.1; done

# Install CloudWatch Agent
yum install -y amazon-cloudwatch-agent

# Create CloudWatch Agent config
cat <<CWCONFIG > /opt/aws/amazon-cloudwatch-agent/bin/config.json
{
  "agent": {
    "metrics_collection_interval": 60,
    "run_as_user": "root"
  },
  "metrics": {
    "append_dimensions": {
      "InstanceId": "\${aws:InstanceId}"
    },
    "metrics_collected": {
      "cpu": {
        "measurement": [
          {"name": "cpu_usage_idle", "rename": "CPUUsageIdle", "unit": "Percent"},
          {"name": "cpu_usage_user", "rename": "CPUUsageUser", "unit": "Percent"},
          {"name": "cpu_usage_system", "rename": "CPUUsageSystem", "unit": "Percent"}
        ],
        "metrics_collection_interval": 60,
        "totalcpu": true
      }
    }
  },
  "logs": {
    "logs_collected": {
      "files": {
        "collect_list": [
          {
            "file_path": "/var/log/nginx/access.log",
            "log_group_name": "nginx/access.log",
            "log_stream_name": "{instance_id}"
          },
          {
            "file_path": "/var/log/nginx/error.log",
            "log_group_name": "nginx/error.log",
            "log_stream_name": "{instance_id}"
          }
        ]
      }
    }
  }
}
CWCONFIG

# Start CloudWatch Agent
/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
  -a fetch-config \
  -m ec2 \
  -c file:/opt/aws/amazon-cloudwatch-agent/bin/config.json \
  -s

systemctl enable amazon-cloudwatch-agent

# install stress-ng tool
sudo amazon-linux-extras install epel -y
sudo yum update -y
sudo yum install stress-ng -y

# simulate CPU load at 70% for 600 seconds
# stress-ng --cpu 4 --cpu-load 70 --timeout 600s

# Test Nginx logs by generating traffic to the server
# generate some traffic to create logs
# for i in {1..300}; do curl -s http://localhost/ > /dev/null; sleep 0.1; done
