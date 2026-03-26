terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "eu-north-1"
}

# ── Variables ─────────────────────────────────────────────────────────────────

variable "key_pair_name" {
  description = "Name of your AWS key pair for SSH access"
  type        = string
}

variable "your_ip" {
  description = "Your IP address for SSH access (e.g. 1.2.3.4/32)"
  type        = string
}

# ── Data ──────────────────────────────────────────────────────────────────────

# Latest Ubuntu 24.04 LTS in eu-north-1
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# ── VPC & Networking ──────────────────────────────────────────────────────────

resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = { Name = "screening-engine-vpc" }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "screening-engine-igw" }
}

resource "aws_subnet" "main" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "eu-north-1a"
  map_public_ip_on_launch = true

  tags = { Name = "screening-engine-subnet" }
}

resource "aws_route_table" "main" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = { Name = "screening-engine-rt" }
}

resource "aws_route_table_association" "main" {
  subnet_id      = aws_subnet.main.id
  route_table_id = aws_route_table.main.id
}

# ── Security Group ────────────────────────────────────────────────────────────

resource "aws_security_group" "screening" {
  name        = "screening-engine-sg"
  description = "Screening Engine access"
  vpc_id      = aws_vpc.main.id

  # SSH — your IP only
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.your_ip]
    description = "SSH"
  }

  # Streamlit dashboard — public
  ingress {
    from_port   = 5000
    to_port     = 5000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Streamlit dashboard"
  }

  # MCP server — your IP only
  ingress {
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = [var.your_ip]
    description = "MCP server"
  }

  # All outbound
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "screening-engine-sg" }
}

# ── EBS Volume for persistent data ───────────────────────────────────────────

resource "aws_ebs_volume" "data" {
  availability_zone = "eu-north-1a"
  size              = 30  # 30 GB for PostgreSQL data
  type              = "gp3"
  encrypted         = true

  tags = { Name = "screening-engine-data" }
}

resource "aws_volume_attachment" "data" {
  device_name = "/dev/xvdf"
  volume_id   = aws_ebs_volume.data.id
  instance_id = aws_instance.screening.id
}

# ── EC2 Instance ──────────────────────────────────────────────────────────────

resource "aws_instance" "screening" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = "t3.small"
  key_name               = var.key_pair_name
  subnet_id              = aws_subnet.main.id
  vpc_security_group_ids = [aws_security_group.screening.id]

  root_block_device {
    volume_size = 20
    volume_type = "gp3"
    encrypted   = true
  }

  user_data = <<-EOF
    #!/bin/bash
    set -e

    # Update system
    apt-get update -y
    apt-get upgrade -y

    # Install Docker
    apt-get install -y ca-certificates curl gnupg
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    apt-get update -y
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    # Add ubuntu user to docker group
    usermod -aG docker ubuntu

    # Install git
    apt-get install -y git

    # Format and mount data volume (wait for it)
    sleep 10
    if [ -b /dev/xvdf ]; then
      mkfs.ext4 /dev/xvdf
      mkdir -p /data
      mount /dev/xvdf /data
      echo '/dev/xvdf /data ext4 defaults,nofail 0 2' >> /etc/fstab
      chown ubuntu:ubuntu /data
    fi

    # Clone repo
    cd /home/ubuntu
    git clone https://github.com/phoenician-capital/screening-engine.git
    chown -R ubuntu:ubuntu screening-engine

    # Create .env placeholder — you fill this in via SSH
    cat > /home/ubuntu/screening-engine/.env.placeholder << 'ENVEOF'
    # Copy this to .env and fill in your values:
    # cp .env.placeholder .env && nano .env

    DB_PASSWORD=phoenician_secure_prod
    DB_HOST=db
    DB_PORT=5432
    DB_NAME=phoenician
    DB_USER=phoenician
    DB_SSL=

    ANTHROPIC_API_KEY=your_key_here
    OPENAI_API_KEY=your_key_here
    PERPLEXITY_API_KEY=your_key_here
    FMP_API_KEY=your_key_here
    GOOGLE_API_KEY=your_key_here
    GROK_API_KEY=your_key_here

    REDIS_HOST=redis
    REDIS_PORT=6379
    ENVEOF

    chown ubuntu:ubuntu /home/ubuntu/screening-engine/.env.placeholder

    # Signal completion
    echo "Bootstrap complete" > /tmp/bootstrap_done
  EOF

  tags = {
    Name    = "screening-engine"
    Project = "PhoenicianCapital"
  }
}

# ── Elastic IP ────────────────────────────────────────────────────────────────

resource "aws_eip" "screening" {
  instance = aws_instance.screening.id
  domain   = "vpc"

  tags = { Name = "screening-engine-eip" }
}

# ── Outputs ───────────────────────────────────────────────────────────────────

output "public_ip" {
  value       = aws_eip.screening.public_ip
  description = "Public IP of the screening engine server"
}

output "public_dns" {
  value       = aws_eip.screening.public_dns
  description = "Public DNS of the screening engine server"
}

output "dashboard_url" {
  value       = "http://${aws_eip.screening.public_ip}:5000"
  description = "Streamlit dashboard URL"
}

output "ssh_command" {
  value       = "ssh -i ~/.ssh/${var.key_pair_name}.pem ubuntu@${aws_eip.screening.public_ip}"
  description = "SSH command to connect"
}
