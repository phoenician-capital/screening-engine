#!/bin/bash
set -e

echo "🚀 Screening Engine Complete Deployment"
echo "========================================"

# Configuration
AWS_REGION="eu-north-1"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
INSTANCE_IP="13.49.7.145"

echo "Account ID: $AWS_ACCOUNT_ID"
echo "Region: $AWS_REGION"
echo "Target: $INSTANCE_IP"

# Step 1: Create ECR repositories
echo ""
echo "📦 Setting up ECR repositories..."
for repo in screening-engine screening-engine-frontend; do
  if ! aws ecr describe-repositories --repository-names $repo --region $AWS_REGION &>/dev/null 2>&1; then
    echo "Creating repository: $repo"
    aws ecr create-repository \
        --repository-name $repo \
        --region $AWS_REGION \
        --image-scanning-configuration scanOnPush=true \
        --encryption-configuration encryptionType=AES256 2>&1 | grep -E "repositoryUri|AlreadyExistsException" || true
  else
    echo "✓ Repository exists: $repo"
  fi
done

# Step 2: Login to ECR
echo ""
echo "🔐 Logging into ECR..."
aws ecr get-login-password --region $AWS_REGION | \
    docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Step 3: Build and push backend
echo ""
echo "🔨 Building backend image..."
docker build -t screening-engine:latest .
ECR_BACKEND="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/screening-engine:latest"
docker tag screening-engine:latest $ECR_BACKEND
echo "📤 Pushing backend to ECR..."
docker push $ECR_BACKEND
echo "✅ Backend image: $ECR_BACKEND"

# Step 4: Build and push frontend
echo ""
echo "🔨 Building frontend image..."
docker build -f Dockerfile.frontend -t screening-engine-frontend:latest .
ECR_FRONTEND="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/screening-engine-frontend:latest"
docker tag screening-engine-frontend:latest $ECR_FRONTEND
echo "📤 Pushing frontend to ECR..."
docker push $ECR_FRONTEND
echo "✅ Frontend image: $ECR_FRONTEND"

# Step 5: Update docker-compose.prod.yml with correct image URIs
echo ""
echo "⚙️  Updating docker-compose configuration..."
sed -i "s|578736536410.dkr.ecr.eu-north-1.amazonaws.com/screening-engine:latest|$ECR_BACKEND|g" docker-compose.prod.yml
sed -i "s|screening-engine-frontend:latest|$ECR_FRONTEND|g" docker-compose.prod.yml

# Step 6: Create deployment bundle
echo ""
echo "📦 Creating deployment bundle..."
mkdir -p /tmp/deploy-bundle
cp docker-compose.prod.yml /tmp/deploy-bundle/docker-compose.yml
cp .env.example /tmp/deploy-bundle/.env.example 2>/dev/null || echo "# Add .env file with your configuration" > /tmp/deploy-bundle/.env
cat > /tmp/deploy-bundle/deploy.sh << 'REMOTE_DEPLOY'
#!/bin/bash
set -e

echo "🚀 Deploying Screening Engine on EC2..."
AWS_REGION="eu-north-1"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

cd /home/ubuntu/screening-engine

# Get ECR login
aws ecr get-login-password --region $AWS_REGION | \
    docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Pull latest compose file
cp /tmp/docker-compose.yml docker-compose.prod.yml

# Stop old services
docker-compose -f docker-compose.prod.yml down || true

# Start new services
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d

# Show status
echo ""
echo "✅ Deployment complete!"
echo ""
docker-compose -f docker-compose.prod.yml ps
echo ""
echo "📊 Services:"
echo "  Backend: http://localhost:8000"
echo "  Frontend: http://localhost:3000"
echo "  PostgreSQL: localhost:5432"
echo "  Redis: localhost:6379"
REMOTE_DEPLOY

chmod +x /tmp/deploy-bundle/deploy.sh

# Step 7: Provide deployment instructions
echo ""
echo "✨ Deployment Bundle Ready!"
echo ""
echo "To deploy to your EC2 instance, run:"
echo ""
echo "  scp -r /tmp/deploy-bundle/* ubuntu@$INSTANCE_IP:/home/ubuntu/screening-engine/"
echo "  ssh ubuntu@$INSTANCE_IP 'cd /home/ubuntu/screening-engine && bash deploy.sh'"
echo ""
echo "Or copy the docker-compose.prod.yml and deploy to your environment:"
echo ""
echo "  ECR_BACKEND=$ECR_BACKEND"
echo "  ECR_FRONTEND=$ECR_FRONTEND"
echo ""
