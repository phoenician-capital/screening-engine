#!/bin/bash

# Production Deployment Monitor
# Usage: ./monitor-deployment.sh

set -e

CLUSTER="phoenician-capital-prod-cluster"
SERVICE="phoenician-capital-prod-api-service"
REGION="eu-north-1"

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║      PHOENICIAN CAPITAL - DEPLOYMENT MONITOR                 ║"
echo "║      Updated: $(date '+%Y-%m-%d %H:%M:%S')                        ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

# Get service info
echo "📊 SERVICE STATUS:"
aws ecs describe-services \
  --cluster "$CLUSTER" \
  --services "$SERVICE" \
  --region "$REGION" \
  --query 'services[0].[serviceName,status,runningCount,desiredCount]' \
  --output text | awk '{print "   Cluster:", $1, "\n   Status:", $2, "\n   Running/Desired:", $3, "/", $4}'
echo ""

# Get deployments
echo "🚀 DEPLOYMENT STATUS:"
aws ecs describe-services \
  --cluster "$CLUSTER" \
  --services "$SERVICE" \
  --region "$REGION" \
  --query 'services[0].deployments[*].[status,runningCount,desiredCount,taskDefinition]' \
  --output text | while read status running desired taskdef; do
    tasknum=$(echo "$taskdef" | rev | cut -d: -f1 | rev)
    echo "   Task Def v$tasknum: $status ($running/$desired running)"
  done
echo ""

# Get running tasks
echo "📋 RUNNING TASKS:"
TASKS=$(aws ecs list-tasks \
  --cluster "$CLUSTER" \
  --service-name "$SERVICE" \
  --region "$REGION" \
  --query 'taskArns[]' \
  --output text 2>/dev/null)

if [ ! -z "$TASKS" ]; then
  aws ecs describe-tasks \
    --cluster "$CLUSTER" \
    --tasks $TASKS \
    --region "$REGION" \
    --query 'tasks[*].[taskArn,lastStatus,desiredStatus,createdAt]' \
    --output text 2>&1 | while read line; do
      echo "   $line"
    done
else
  echo "   No tasks running"
fi
echo ""

# Get recent events
echo "📝 RECENT EVENTS (Last 5):"
aws ecs describe-services \
  --cluster "$CLUSTER" \
  --services "$SERVICE" \
  --region "$REGION" \
  --query 'services[0].events[:5].[createdAt,message]' \
  --output text 2>&1 | while read timestamp msg; do
    echo "   [$timestamp] $msg" | cut -c 1-110
  done
echo ""

# Summary
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "✅ v38 (STABLE)   - Currently serving traffic"
echo "⚠️  v39 (NEW)     - Failing health checks"
echo ""
echo "💡 Next steps:"
echo "   1. Wait 10-15 min for Docker build to complete"
echo "   2. Check CloudWatch logs if v39 still fails"
echo "   3. Rollback if needed (see deployment status)"
echo "╚═══════════════════════════════════════════════════════════════╝"
