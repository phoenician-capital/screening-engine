# 🚀 Deployment Guide - Phoenician Screening Engine

**Status:** Production Ready  
**Deployment Target:** AWS EC2 + Docker  
**Region:** eu-north-1  
**Date:** March 31, 2026

---

## 📋 Pre-Deployment Checklist

Before deploying, ensure you have:

- [ ] AWS Account with credentials configured
- [ ] Terraform installed locally
- [ ] Docker and Docker Compose installed
- [ ] All API keys ready (Anthropic, OpenAI, FMP, Google, etc.)
- [ ] PostgreSQL connection details
- [ ] Git repository access
- [ ] SSH key pair for EC2 access

---

## 🌍 Infrastructure Overview

```
┌─────────────────────────────────────────┐
│         AWS eu-north-1 Region           │
├─────────────────────────────────────────┤
│                                         │
│  VPC (10.0.0.0/16)                     │
│  ├─ Subnet (10.0.1.0/24)               │
│  │  └─ EC2 Instance (t3.small)         │
│  │     ├─ Backend API (port 8000)      │
│  │     ├─ Frontend (port 5000)         │
│  │     ├─ PostgreSQL (port 5432)       │
│  │     ├─ Redis (port 6379)            │
│  │     └─ 30GB EBS Volume              │
│  │                                      │
│  └─ Elastic IP (static public IP)      │
│                                         │
│  Security Group                         │
│  ├─ SSH (22) - Your IP only            │
│  ├─ API (8000) - Your IP only          │
│  ├─ Dashboard (5000) - Public          │
│  └─ All outbound                       │
│                                         │
└─────────────────────────────────────────┘
```

---

## 📦 Service Stack

**On the EC2 instance, Docker Compose will run:**

```
Container 1: PostgreSQL 15
  ├─ Database: phoenician
  ├─ Volume: EBS /data/postgres
  └─ Port: 5432 (internal only)

Container 2: Redis 7
  ├─ Cache & session store
  ├─ Volume: /data/redis
  └─ Port: 6379 (internal only)

Container 3: Backend API (Python)
  ├─ FastAPI server
  ├─ Port: 8000 (restricted to your IP)
  └─ Environment: .env configured

Container 4: Frontend (React)
  ├─ Static build served via Nginx
  ├─ Port: 5000 (public)
  └─ Auto-deploys from GitHub
```

---

## 🚀 Step-by-Step Deployment

### Step 1: Prepare AWS Infrastructure (Terraform)

```bash
cd terraform

# Initialize Terraform
terraform init

# Preview what will be created
terraform plan

# Create infrastructure
terraform apply

# Output will show:
# public_ip = "1.2.3.4"
# Save this IP!
```

**Time:** ~3 minutes  
**Cost:** ~€10-15/month (t3.small)

### Step 2: Configure Environment

After Terraform completes, SSH into the instance:

```bash
# SSH into EC2 instance
ssh -i ~/.ssh/phoenician-bastion.pem ubuntu@<public_ip>

# Configure environment
cd screening-engine
cp .env.placeholder .env
nano .env

# Fill in all API keys:
# - ANTHROPIC_API_KEY=sk-...
# - OPENAI_API_KEY=sk-...
# - FMP_API_KEY=...
# - GOOGLE_API_KEY=...
# - GROK_API_KEY=...
# - PERPLEXITY_API_KEY=...
```

### Step 3: Deploy Backend & Database

```bash
# From the repo root
docker compose up -d

# Watch logs
docker compose logs -f

# Expected output:
# ✓ PostgreSQL initialized
# ✓ Redis started
# ✓ API server listening on 0.0.0.0:8000
# ✓ Frontend served on 0.0.0.0:5000
```

### Step 4: Initialize Database

```bash
# SSH into DB container
docker exec -it screening-engine-db-1 psql -U phoenician -d phoenician

# Run migrations
psql -U phoenician -d phoenician < src/db/migrations/007_learned_patterns.sql
psql -U phoenician -d phoenician < src/db/migrations/008_selection_metrics.sql

# Verify tables
\dt
# Should show all tables including selection_learned_patterns

# Exit
\q
```

### Step 5: Verify Deployment

```bash
# Test API endpoint
curl http://<public_ip>:8000/api/v1/screening/status

# Expected response:
# {"running": false, "done": false, ...}

# Test frontend
open http://<public_ip>:5000/screening

# Should see: Phoenician Screening Engine dashboard
```

---

## 🔄 Continuous Deployment (GitHub to EC2)

The system auto-deploys from GitHub using webhooks:

```
GitHub push
    ↓
GitHub webhook triggers EC2
    ↓
EC2 pulls latest code
    ↓
Docker images rebuild
    ↓
Services restart
    ↓
Zero downtime deployment
```

**Setup webhook:**

1. Go to GitHub repo → Settings → Webhooks
2. Add webhook: `http://<public_ip>:8001/webhook`
3. Content type: `application/json`
4. Events: `push`
5. Active: ✓

---

## 📊 Monitoring & Logs

### Check Service Status

```bash
# View all containers
docker ps

# View logs (all services)
docker compose logs -f

# View specific service
docker compose logs -f api
docker compose logs -f db
docker compose logs -f redis

# Tail latest 100 lines
docker compose logs --tail=100 api
```

### Database Monitoring

```bash
# Connect to DB
docker exec -it screening-engine-db-1 psql -U phoenician -d phoenician

# Check tables
SELECT COUNT(*) FROM recommendations;
SELECT COUNT(*) FROM feedback;
SELECT COUNT(*) FROM selection_learned_patterns;

# Performance queries
EXPLAIN ANALYZE SELECT * FROM recommendations ORDER BY rank_score DESC;
```

### API Health Check

```bash
curl -s http://localhost:8000/api/v1/screening/status | jq .

curl -s http://localhost:8000/api/v1/portfolio | jq .

curl -s http://localhost:8000/api/v1/stats | jq .
```

---

## 🔐 Security Checklist

- [ ] SSH access: Your IP only
- [ ] API access: Your IP only (port 8000)
- [ ] Frontend: Public (port 5000)
- [ ] Database: Internal only (not exposed)
- [ ] Redis: Internal only (not exposed)
- [ ] EBS volumes: Encrypted
- [ ] Backup: Daily snapshots scheduled
- [ ] API keys: In .env (not in code)
- [ ] Git credentials: Via SSH keys

### Enable Automated Backups

```bash
# Backup database daily
docker exec screening-engine-db-1 pg_dump -U phoenician phoenician > /data/backups/db_$(date +%Y%m%d).sql

# Add to crontab
# 0 2 * * * docker exec screening-engine-db-1 pg_dump -U phoenician phoenician > /data/backups/db_$(date +\%Y\%m\%d).sql
```

---

## 🧪 Post-Deployment Testing

### Test 1: Screening Run

```bash
curl -X POST http://<public_ip>:8000/api/v1/screening/run \
  -H "Content-Type: application/json" \
  -d '{"max_companies": 10}'

# Monitor progress
curl http://<public_ip>:8000/api/v1/screening/status
```

### Test 2: Feedback Submission

```bash
curl -X POST http://<public_ip>:8000/api/v1/recommendations/AXON/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "action": "reject",
    "reason": "Too expensive",
    "notes": "Valuation at 30x P/E, would revisit at 22x"
  }'

# Expected response
# {"ok": true, "ticker": "AXON", "action": "reject"}
```

### Test 3: Real-Time Events (SSE)

```bash
# In one terminal, start screening
curl -X POST http://<public_ip>:8000/api/v1/screening/run

# In another terminal, listen to events
curl http://<public_ip>:8000/api/v1/screening/events

# Should see:
# data: {"type": "screening_started", ...}
# data: {"type": "discovery_complete", ...}
# etc
```

### Test 4: Frontend UI

Open browser to: `http://<public_ip>:5000/screening`

- [ ] Dashboard loads
- [ ] Click "Execute Screening Run"
- [ ] Watch agents work in real-time
- [ ] See results appear
- [ ] Toggle Progress ↔ Agents view
- [ ] Submit feedback on companies

---

## 🆘 Troubleshooting

### Issue: API returns 502 Bad Gateway

```bash
# Check if containers are running
docker ps

# If not, restart
docker compose restart api

# Check logs
docker compose logs api

# Might need to rebuild
docker compose up -d --build
```

### Issue: Database connection failed

```bash
# Check DB container
docker compose logs db

# Check .env file has correct credentials
cat .env | grep DB_

# Restart DB
docker compose restart db

# Wait 30 seconds for startup
sleep 30

# Test connection
docker exec screening-engine-db-1 psql -U phoenician -c "SELECT 1"
```

### Issue: Out of disk space

```bash
# Check disk usage
df -h

# Clean up Docker
docker system prune -a

# Check data volume
du -sh /data

# If DB is too large, backup and purge old data
docker exec screening-engine-db-1 pg_dump -U phoenician phoenician > /data/backup.sql
```

### Issue: High CPU usage

```bash
# See what's running
docker stats

# If API is high, check for long-running screenings
curl http://localhost:8000/api/v1/screening/status

# If query is stuck, restart API
docker compose restart api
```

---

## 📈 Scaling the System

As usage grows:

### Vertical Scaling (bigger instance)

```bash
# Change instance type in terraform
# edit: instance_type = "t3.medium" (or larger)

# Redeploy
terraform apply

# Time: ~5 minutes downtime
```

### Separate Database (RDS)

```bash
# Move PostgreSQL to AWS RDS
# Update .env with RDS endpoint
DB_HOST=phoenician-db.c9akciq32.eu-north-1.rds.amazonaws.com

# Redeploy backend
docker compose up -d --build
```

### Separate Frontend (CloudFront + S3)

```bash
# Build static React app
npm run build

# Upload to S3
aws s3 sync build s3://phoenician-frontend-prod/

# Configure CloudFront CDN
# Point to S3 bucket

# Results: Much faster frontend, lower latency
```

---

## 📊 Monitoring Dashboard

### Useful Queries

**Database size:**
```sql
SELECT pg_size_pretty(pg_database_size('phoenician'));
```

**Recommendations count:**
```sql
SELECT DATE(created_at), COUNT(*) FROM recommendations GROUP BY DATE(created_at);
```

**Screening performance:**
```sql
SELECT 
  DATE(run_start) as date,
  COUNT(*) as runs,
  AVG(EXTRACT(EPOCH FROM (run_end - run_start))) as avg_seconds,
  SUM(tickers_scored) as total_scored
FROM scoring_runs
GROUP BY DATE(run_start)
ORDER BY date DESC;
```

---

## 🚨 Alert Thresholds

Set up alerts for:

- API response time > 5 seconds
- Database query time > 2 seconds
- Disk usage > 80%
- Memory usage > 80%
- Error rate > 1%
- Screening runtime > 20 minutes
- Feedback processing failures

---

## 📚 Documentation for Team

Share these with your team:

1. **README.md** — How to use the system
2. **DEPLOYMENT_GUIDE.md** — This document (ops team)
3. **DEPLOYMENT_READY_CHECKLIST.md** — Pre-launch checklist
4. **REAL_TIME_VISUALIZATION_GUIDE.md** — UI/UX guide
5. **FEEDBACK_ENHANCEMENT_COMPLETE.md** — Feedback system docs

---

## 🎉 You're Live!

Once deployed:

1. ✅ System is live at: `http://<public_ip>:5000`
2. ✅ API available at: `http://<public_ip>:8000/api/v1/...`
3. ✅ Real-time events streaming from: `http://<public_ip>:8000/api/v1/screening/events`
4. ✅ Analyst can start running screenings
5. ✅ System learns from feedback immediately
6. ✅ Cost savings begin accruing

---

## 🔄 Deployment Checklist

- [ ] Terraform infrastructure deployed
- [ ] EC2 instance created with Elastic IP
- [ ] Security groups configured
- [ ] .env file configured with all API keys
- [ ] Docker containers running
- [ ] Database migrations applied
- [ ] API endpoints tested
- [ ] Frontend loads in browser
- [ ] Screening run completes successfully
- [ ] Feedback submission works
- [ ] Real-time events stream correctly
- [ ] Team has access and knows how to use it
- [ ] Backups configured
- [ ] Monitoring alerts set up

---

## 📞 Support

If issues arise:

1. Check logs: `docker compose logs -f`
2. Verify .env: `cat .env`
3. Restart services: `docker compose restart`
4. Check README.md for troubleshooting
5. Review SYSTEM_READY_TEST_GUIDE.md

---

**Deployment Date:** March 31, 2026  
**System:** Phoenician Screening Engine v2.0  
**Status:** Production Ready ✅

🚀 **The bomb is live!** 🚀
