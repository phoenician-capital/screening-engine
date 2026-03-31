#!/bin/bash
set -e

echo "🚀 Screening Engine Deployment"
echo "=============================="

# Configuration
AWS_REGION="eu-north-1"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPO="screening-engine"
INSTANCE_ID="i-08bd901b0a0efefad"
INSTANCE_IP="13.49.7.145"

echo "Account ID: $AWS_ACCOUNT_ID"
echo "Region: $AWS_REGION"
echo "Instance: $INSTANCE_ID ($INSTANCE_IP)"

# Step 1: Create ECR repository if needed
echo ""
echo "📦 Setting up ECR repository..."
if ! aws ecr describe-repositories --repository-names $ECR_REPO --region $AWS_REGION &>/dev/null; then
    echo "Creating ECR repository..."
    aws ecr create-repository \
        --repository-name $ECR_REPO \
        --region $AWS_REGION \
        --image-scanning-configuration scanOnPush=true \
        --encryption-configuration encryptionType=AES256
fi

# Step 2: Build and push Docker image
echo ""
echo "🔨 Building and pushing Docker image..."
aws ecr get-login-password --region $AWS_REGION | \
    docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

docker build -t $ECR_REPO:latest .
ECR_URI="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:latest"
docker tag $ECR_REPO:latest $ECR_URI
docker push $ECR_URI

echo "✅ Image pushed: $ECR_URI"

# Step 3: Deploy to EC2 via SSM Session Manager (no SSH key needed)
echo ""
echo "📤 Deploying to EC2 instance..."
cat > /tmp/deploy-commands.sh << 'DEPLOY_EOF'
#!/bin/bash
set -e

AWS_REGION="eu-north-1"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPO="screening-engine"

cd /home/ubuntu/screening-engine

# Update image in docker-compose
sed -i "s|image: .*:latest|image: $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:latest|g" docker-compose.yml

# Pull latest code
git pull origin main || true

# Login to ECR
aws ecr get-login-password --region $AWS_REGION | \
    docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Deploy with docker-compose
docker-compose down || true
docker-compose up -d

echo "✅ Deployment complete!"
docker-compose ps
DEPLOY_EOF

# Send script to EC2 via SSM
chmod +x /tmp/deploy-commands.sh
aws ssm send-command \
    --instance-ids $INSTANCE_ID \
    --document-name "AWS-RunShellScript" \
    --parameters 'commands=cat > /tmp/deploy.sh && bash /tmp/deploy.sh' \
    --region $AWS_REGION \
    --output text || echo "⚠️  SSM deployment skipped (no agent or permissions)"

echo ""
echo "✨ Deployment initiated!"
echo ""
echo "📊 To check logs:"
echo "   aws logs tail /docker/screening-engine --follow --region $AWS_REGION"
echo ""
echo "📈 To check services:"
echo "   ssh ubuntu@$INSTANCE_IP  # (if you have SSH key)"
echo "   docker-compose -f /home/ubuntu/screening-engine/docker-compose.yml ps"
