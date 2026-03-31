# Screening Engine Deployment (Docker + ECS)

## Architecture

```
Your Code → Docker Build → ECR Push → ECS Update → Running Container on EC2
```

## Prerequisites

1. **AWS CLI configured:**
   ```bash
   aws configure
   # Enter: Access Key, Secret Key, Region (eu-north-1)
   ```

2. **Docker installed:**
   ```bash
   docker --version
   ```

## Quick Start

### Step 1: Set up ECS infrastructure (one-time)

```bash
cd "c:/Phoenician Capital/Screening_Engine"
bash setup-ecs.sh
```

This creates:
- ✅ ECS Cluster
- ✅ ECS Task Definition
- ✅ ECS Service
- ✅ CloudWatch Logs
- ✅ Alarms

### Step 2: Deploy (every time you push to main)

**Option A: Automatic (GitHub Actions)**
- Just `git push origin main`
- GitHub Actions builds, pushes to ECR, updates ECS
- Deployment happens automatically

**Option B: Manual**
```bash
bash deploy.sh
```

This:
- ✅ Logs into AWS ECR
- ✅ Builds Docker image
- ✅ Pushes to ECR repository
- ✅ Updates ECS service (rolling deployment)
- ✅ Waits for deployment to complete

## Monitoring

### View logs (real-time)
```bash
aws logs tail /ecs/screening-engine --follow --region eu-north-1
```

### Check deployment status
```bash
aws ecs describe-services \
  --cluster screening-engine-cluster \
  --services screening-engine-service \
  --region eu-north-1 \
  --query 'services[0].[desiredCount,runningCount,deployments[0].status]'
```

### List running tasks
```bash
aws ecs list-tasks \
  --cluster screening-engine-cluster \
  --region eu-north-1
```

### View task details
```bash
aws ecs describe-tasks \
  --cluster screening-engine-cluster \
  --tasks <task-arn> \
  --region eu-north-1
```

## Troubleshooting

### Deployment stuck or failing?

1. **Check logs:**
   ```bash
   aws logs tail /ecs/screening-engine --follow --region eu-north-1
   ```

2. **Check task status:**
   ```bash
   aws ecs describe-tasks \
     --cluster screening-engine-cluster \
     --tasks <task-arn> \
     --region eu-north-1 \
     --query 'tasks[0].lastStatus'
   ```

3. **View stopped reason:**
   ```bash
   aws ecs describe-tasks \
     --cluster screening-engine-cluster \
     --tasks <task-arn> \
     --region eu-north-1 \
     --query 'tasks[0].stoppedReason'
   ```

### ECR image issues?

1. **List ECR images:**
   ```bash
   aws ecr describe-images \
     --repository-name screening-engine \
     --region eu-north-1
   ```

2. **Delete old images:**
   ```bash
   aws ecr batch-delete-image \
     --repository-name screening-engine \
     --image-ids imageTag=old-tag \
     --region eu-north-1
   ```

## GitHub Actions Secrets Setup

To enable automatic deployment on push:

1. Go to: https://github.com/phoenician-capital/screening-engine/settings/secrets/actions

2. Add these secrets:
   - `AWS_ACCESS_KEY_ID`: Your AWS access key
   - `AWS_SECRET_ACCESS_KEY`: Your AWS secret key

3. That's it! Every push to main will auto-deploy.

## Cost Estimate

- **ECS (on-demand)**: ~$0.02/hour
- **ECR storage**: ~$0.10/GB/month
- **CloudWatch Logs**: ~$0.50/GB ingested
- **Total**: ~$15-20/month

## Rollback

If deployment fails:

```bash
aws ecs update-service \
  --cluster screening-engine-cluster \
  --services screening-engine-service \
  --task-definition screening-engine:N \
  --region eu-north-1
```

Where N is the previous task definition number.

---

**That's it!** Your API is now running in production on ECS with full CI/CD pipeline. 🚀
