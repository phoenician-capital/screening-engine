#!/bin/bash
set -e

echo "🚀 Setting up auto-deploy infrastructure..."

# Get AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "Account ID: $ACCOUNT_ID"

# Deploy CloudFormation stack
echo "Deploying CloudFormation stack..."
aws cloudformation create-stack \
  --stack-name screening-engine-deploy \
  --template-body file://deploy-infra.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --region eu-north-1 || echo "Stack already exists"

echo "Waiting for stack..."
aws cloudformation wait stack-create-complete \
  --stack-name screening-engine-deploy \
  --region eu-north-1 2>/dev/null || true

# Get webhook URL
WEBHOOK_URL=$(aws cloudformation describe-stacks \
  --stack-name screening-engine-deploy \
  --region eu-north-1 \
  --query 'Stacks[0].Outputs[?OutputKey==`WebhookUrl`].OutputValue' \
  --output text)

echo ""
echo "✅ Auto-deploy infrastructure created!"
echo ""
echo "Webhook URL: $WEBHOOK_URL"
echo ""
echo "Next steps:"
echo "1. Go to: https://github.com/phoenician-capital/screening-engine/settings/hooks"
echo "2. Click 'Add webhook'"
echo "3. Paste this URL: $WEBHOOK_URL"
echo "4. Set Content type to: application/json"
echo "5. Select: 'Let me select individual events'"
echo "6. Check only: 'Push events'"
echo "7. Check: 'Active'"
echo "8. Click 'Add webhook'"
echo ""
echo "Done! Every push to main will auto-deploy to EC2 🚀"
