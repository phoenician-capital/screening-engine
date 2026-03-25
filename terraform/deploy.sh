#!/bin/bash
# Run this after terraform apply to finish setup on the EC2 instance
# Usage: bash deploy.sh <public_ip> <key_pair_name>

set -e

IP=$1
KEY=$2

if [ -z "$IP" ] || [ -z "$KEY" ]; then
  echo "Usage: bash deploy.sh <public_ip> <key_pair_name>"
  echo "Example: bash deploy.sh 13.48.1.2 screening-engine-key"
  exit 1
fi

echo "Deploying to $IP..."

# Copy .env file
echo "Copying .env..."
scp -i ~/.ssh/${KEY}.pem -o StrictHostKeyChecking=no \
  ../.env ubuntu@${IP}:/home/ubuntu/screening-engine/.env

# Start Docker Compose
echo "Starting services..."
ssh -i ~/.ssh/${KEY}.pem -o StrictHostKeyChecking=no ubuntu@${IP} << 'SSHEOF'
  cd /home/ubuntu/screening-engine

  # Update docker-compose to use /data for postgres volume
  sed -i 's|pgdata:/var/lib/postgresql/data|/data/pgdata:/var/lib/postgresql/data|g' docker-compose.yml

  # Start all services
  docker compose up -d --build

  echo "Services starting..."
  sleep 10
  docker compose ps
SSHEOF

echo ""
echo "Done! Dashboard available at: http://${IP}:5000"
echo "SSH access: ssh -i ~/.ssh/${KEY}.pem ubuntu@${IP}"
