#!/bin/bash
set -e

echo "🚀 Setting up ECS Infrastructure"
echo "=================================="

AWS_REGION="eu-north-1"
STACK_NAME="screening-engine-ecs"

# Deploy CloudFormation stack
echo ""
echo "📦 Deploying CloudFormation stack..."
aws cloudformation deploy \
    --template-file ecs-infrastructure.yaml \
    --stack-name $STACK_NAME \
    --region $AWS_REGION \
    --no-fail-on-empty-changeset

echo "✅ CloudFormation stack deployed"

# Get outputs
echo ""
echo "📊 Stack outputs:"
aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $AWS_REGION \
    --query 'Stacks[0].Outputs' \
    --output table

echo ""
echo "✨ ECS infrastructure ready!"
echo ""
echo "Next: Run deploy.sh to build and push your Docker image"
