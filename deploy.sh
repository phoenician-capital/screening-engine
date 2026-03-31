#!/bin/bash
set -e

echo "🚀 Screening Engine Deployment (Docker → ECR → ECS)"
echo "=================================================="

# Configuration
AWS_REGION="eu-north-1"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPO="screening-engine"
ECS_CLUSTER="screening-engine-cluster"
ECS_SERVICE="screening-engine-service"
IMAGE_TAG="latest"

echo "Account ID: $AWS_ACCOUNT_ID"
echo "Region: $AWS_REGION"
echo "ECR Repo: $ECR_REPO"

# Step 1: Check if ECR repository exists, create if not
echo ""
echo "📦 Checking ECR repository..."
if ! aws ecr describe-repositories --repository-names $ECR_REPO --region $AWS_REGION &>/dev/null; then
    echo "Creating ECR repository..."
    aws ecr create-repository \
        --repository-name $ECR_REPO \
        --region $AWS_REGION \
        --image-scanning-configuration scanOnPush=true \
        --encryption-configuration encryptionType=AES \
        || true
fi

# Step 2: Get ECR login token and login to Docker
echo ""
echo "🔐 Logging into AWS ECR..."
aws ecr get-login-password --region $AWS_REGION | \
    docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Step 3: Build Docker image
echo ""
echo "🔨 Building Docker image..."
docker build -t $ECR_REPO:$IMAGE_TAG .
echo "✅ Docker image built"

# Step 4: Tag image for ECR
echo ""
echo "🏷️  Tagging image for ECR..."
ECR_URI="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:$IMAGE_TAG"
docker tag $ECR_REPO:$IMAGE_TAG $ECR_URI

# Step 5: Push to ECR
echo ""
echo "📤 Pushing to ECR..."
docker push $ECR_URI
echo "✅ Image pushed to ECR"

# Step 6: Update ECS service
echo ""
echo "🔄 Updating ECS service..."
TASK_DEFINITION=$(aws ecs describe-services \
    --cluster $ECS_CLUSTER \
    --services $ECS_SERVICE \
    --region $AWS_REGION \
    --query 'services[0].taskDefinition' \
    --output text)

echo "Task Definition: $TASK_DEFINITION"

# Force new deployment
aws ecs update-service \
    --cluster $ECS_CLUSTER \
    --service $ECS_SERVICE \
    --force-new-deployment \
    --region $AWS_REGION > /dev/null

echo "✅ ECS service updated (rolling deployment started)"

# Step 7: Wait for deployment
echo ""
echo "⏳ Waiting for deployment to complete (this may take 2-3 minutes)..."
ATTEMPTS=0
MAX_ATTEMPTS=60

while [ $ATTEMPTS -lt $MAX_ATTEMPTS ]; do
    RUNNING=$(aws ecs describe-services \
        --cluster $ECS_CLUSTER \
        --services $ECS_SERVICE \
        --region $AWS_REGION \
        --query 'services[0].runningCount' \
        --output text)
    
    DESIRED=$(aws ecs describe-services \
        --cluster $ECS_CLUSTER \
        --services $ECS_SERVICE \
        --region $AWS_REGION \
        --query 'services[0].desiredCount' \
        --output text)
    
    echo "Running: $RUNNING / Desired: $DESIRED"
    
    if [ "$RUNNING" -eq "$DESIRED" ]; then
        echo "✅ Deployment complete!"
        break
    fi
    
    sleep 3
    ATTEMPTS=$((ATTEMPTS + 1))
done

if [ $ATTEMPTS -eq $MAX_ATTEMPTS ]; then
    echo "⚠️  Deployment timeout (still rolling out)"
fi

echo ""
echo "✨ Deployment finished!"
echo ""
echo "📊 View logs with:"
echo "   aws logs tail /ecs/screening-engine --follow --region $AWS_REGION"
echo ""
echo "📈 Check status with:"
echo "   aws ecs describe-services --cluster $ECS_CLUSTER --services $ECS_SERVICE --region $AWS_REGION"
