#!/bin/bash
set -e

INSTANCE_IP="13.49.7.145"
KEY_PATH="${1:-$HOME/.ssh/phoenician-bastion.pem}"

if [ ! -f "$KEY_PATH" ]; then
  echo "❌ SSH key not found: $KEY_PATH"
  echo "Usage: $0 [/path/to/ssh/key]"
  exit 1
fi

echo "🚀 Deploying to EC2 Instance"
echo "============================"
echo "Instance: ubuntu@$INSTANCE_IP"
echo "Key: $KEY_PATH"

# Check SSH connectivity
echo ""
echo "🔐 Testing SSH connection..."
if ! ssh -i "$KEY_PATH" -o ConnectTimeout=5 ubuntu@$INSTANCE_IP "echo 'SSH OK'" 2>/dev/null; then
  echo "❌ Cannot connect to $INSTANCE_IP via SSH"
  echo "Check:"
  echo "  1. Instance is running"
  echo "  2. Security group allows port 22"
  echo "  3. SSH key is correct"
  exit 1
fi
echo "✅ SSH connection OK"

# Copy deployment files
echo ""
echo "📤 Copying files to EC2..."
ssh -i "$KEY_PATH" ubuntu@$INSTANCE_IP "mkdir -p /home/ubuntu/screening-engine"

scp -i "$KEY_PATH" -r /tmp/deploy-bundle/* ubuntu@$INSTANCE_IP:/home/ubuntu/screening-engine/ 2>/dev/null || true
scp -i "$KEY_PATH" docker-compose.prod.yml ubuntu@$INSTANCE_IP:/home/ubuntu/screening-engine/ 2>/dev/null || true

echo "✅ Files copied"

# Deploy
echo ""
echo "🚀 Running deployment on EC2..."

# Create a temporary script file
TEMP_DEPLOY_SCRIPT=$(mktemp)
cat > "$TEMP_DEPLOY_SCRIPT" << 'REMOTE_SCRIPT'
#!/bin/bash
set -e

echo "📦 Updating repository..."
cd /home/ubuntu/screening-engine
git pull origin main 2>/dev/null || true

echo "🔐 Logging into ECR..."
AWS_REGION="eu-north-1"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Get ECR password and login
ECR_PASSWORD=$(aws ecr get-login-password --region $AWS_REGION)
echo "$ECR_PASSWORD" | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

echo "🛑 Stopping old services..."
docker compose -f docker-compose.prod.yml down 2>/dev/null || true

echo "📥 Pulling latest images..."
docker compose -f docker-compose.prod.yml pull

echo "🚀 Starting services..."
docker compose -f docker-compose.prod.yml up -d

# Wait for services to be healthy
echo ""
echo "⏳ Waiting for services to start..."
for i in {1..30}; do
  if curl -s http://localhost:8000/api/v1/screening/status > /dev/null 2>&1; then
    echo "✅ Backend is healthy"
    break
  fi
  echo "  Attempt $i/30..."
  sleep 2
done

echo ""
echo "✨ Deployment complete!"
echo ""
docker compose -f docker-compose.prod.yml ps
echo ""
echo "📊 Services running on:"
echo "  Backend: http://localhost:8000"
echo "  Frontend: http://localhost:3000"
echo "  Logs: docker compose -f docker-compose.prod.yml logs -f"
REMOTE_SCRIPT

# Copy script to EC2 and execute
scp -i "$KEY_PATH" "$TEMP_DEPLOY_SCRIPT" ubuntu@$INSTANCE_IP:/tmp/deploy-remote.sh
ssh -i "$KEY_PATH" ubuntu@$INSTANCE_IP "bash /tmp/deploy-remote.sh"

# Clean up temp script
rm "$TEMP_DEPLOY_SCRIPT"

echo ""
echo "✅ Deployment finished!"
echo ""
echo "🌐 Access your services:"
echo "   Frontend: http://$INSTANCE_IP:3000"
echo "   API: http://$INSTANCE_IP:8000"
echo ""
echo "📊 Check logs:"
echo "   ssh -i $KEY_PATH ubuntu@$INSTANCE_IP 'docker compose -f /home/ubuntu/screening-engine/docker-compose.prod.yml logs -f'"
echo ""
