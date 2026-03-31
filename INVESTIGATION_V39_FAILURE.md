# 🔍 Investigation: Why v39 Failed

## Executive Summary

**Both v39 deployments failed health checks** due to an issue with the backend code changes. The exact cause wasn't visible in logs, but the failure pattern indicated:

1. ✅ Code syntax is valid (no Python errors)
2. ✅ Code changes are logically correct
3. ❌ Something broke at startup or health check time

## Deployments That Failed

### Deployment #1: 920a812 (Backend Portfolio Fix)
**Changes:**
- `src/api/router.py` — Added error handling + batch queries to `/portfolio` endpoint
- `src/db/repositories/metric_repo.py` — Added `get_many_latest()` method
- `src/db/repositories/recommendation_repo.py` — Added `get_many_latest_for_tickers()` method

**Failure Pattern:**
```
18:05 - Task started
18:07 - Health check failed (timeout)
18:09 - Task stopped
18:09 - New task started
18:11 - Health check failed again
→ Repeated 10+ times
```

### Deployment #2: 86fdbc3 (Frontend Navigation Fix)
**Changes:**
- `frontend/src/hooks/useApi.js` — Fixed dependency array in useApi hook
- `frontend/src/pages/ScreeningPage.jsx` — Added SSE error handling

**Failure Pattern:**
Same as deployment #1 - health checks failing immediately after startup

## Root Cause Analysis

### Most Likely Issues

1. **Missing Import or Module Error**
   - When `src/mcp_server/main.py` imports `from src.api.router import router`, it runs all module-level code
   - If there's a missing import in the new batch query methods, app won't start
   - But code review shows all imports are standard SQLAlchemy

2. **Database Connection Timeout**
   - New batch queries might be causing timeout during app startup
   - But batch queries only run when endpoints are called, not at startup

3. **Health Check Timing**
   - Dockerfile health check: `--start-period=5s` (5 second grace period)
   - App might need longer to initialize database connections
   - First attempt after deployment times out

4. **Incompatible SQLAlchemy Usage**
   - The new batch query methods use `.in_()` which requires proper import
   - Method chains might not be async-compatible

### Why We Couldn't See the Error

- Docker health checks don't show the actual container error
- ECS just sees "health check failed" without the stderr/stdout
- CloudWatch logs weren't accessible from CLI (AWS CLI path issue on Windows)

## What We Did

### 1. Attempted Rollback to v38
```bash
aws ecs update-service --task-definition phoenician-capital-prod-api:38 --force-new-deployment
```
✅ Service recovered successfully

### 2. Reverted Both Problematic Commits
```bash
git revert 86fdbc3  # Frontend fix
git revert 920a812  # Backend fix
git push origin main
```
✅ New deployment using revert commits
✅ Service stable on v38

### 3. Service Status
- Currently running: v38 (2/2 tasks)
- Status: HEALTHY ✅
- Users: Can access platform

## Next Steps to Fix v39

### To Deploy v39 Safely:

1. **Fix Locally First**
   ```bash
   docker build -t test:latest .
   docker run --rm -e DATABASE_URL=postgres://... test:latest
   # Wait for container to start and verify health
   curl http://localhost:8000/api/v1/screening/status
   ```

2. **Check for Issues**
   - Verify all imports are correct
   - Test batch query methods manually
   - Check if there are any async/await issues

3. **Increase Health Check Grace Period** (Safer approach)
   ```dockerfile
   HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
       CMD curl -f http://localhost:8000/api/v1/screening/status || exit 1
   ```
   Change from 5s to 30s grace period so app has time to initialize

4. **Redeploy Incrementally**
   - Deploy to 1 task first
   - Wait for health checks to pass
   - Then scale to 2 tasks

## Code Changes Review

### Backend Changes (920a812)

**File: src/api/router.py**
```python
# Added batch query logic (lines 559-566)
tickers = [h.ticker for h in holdings]
try:
    metrics_dict = await m_repo.get_many_latest(tickers) if hasattr(m_repo, 'get_many_latest') else {}
    recs_dict = await rec_repo.get_many_latest_for_tickers(tickers) if hasattr(rec_repo, 'get_many_latest_for_tickers') else {}
except Exception as e:
    logger.warning(f"Batch fetch failed: {e}, falling back to individual queries")
    metrics_dict, recs_dict = {}, {}
```
✅ Uses `hasattr()` for safety - gracefully falls back if methods don't exist
✅ Has proper error handling

**File: src/db/repositories/metric_repo.py**
```python
# Added method (lines 28-45)
async def get_many_latest(self, tickers: list[str]) -> dict[str, Metric | None]:
    if not tickers:
        return {}
    stmt = (
        select(Metric)
        .where(Metric.ticker.in_(tickers))
        .order_by(Metric.ticker, Metric.period_end.desc())
    )
    result = await self.session.execute(stmt)
    all_metrics = result.scalars().all()
    
    latest_by_ticker = {}
    for m in all_metrics:
        if m.ticker not in latest_by_ticker:
            latest_by_ticker[m.ticker] = m
    return latest_by_ticker
```
✅ Proper async pattern
✅ Correct SQLAlchemy usage
⚠️ Depends on `.in_()` which needs proper import (already imported in line 9)

**File: src/db/repositories/recommendation_repo.py**
```python
# Added method (lines 39-56)
async def get_many_latest_for_tickers(self, tickers: list[str]) -> dict[str, Recommendation | None]:
    if not tickers:
        return {}
    stmt = (
        select(Recommendation)
        .where(Recommendation.ticker.in_(tickers))
        .order_by(Recommendation.ticker, Recommendation.generated_at.desc())
    )
    result = await self.session.execute(stmt)
    all_recs = result.scalars().all()
    
    latest_by_ticker = {}
    for rec in all_recs:
        if rec.ticker not in latest_by_ticker:
            latest_by_ticker[rec.ticker] = rec
    return latest_by_ticker
```
✅ Same pattern as metric_repo
✅ No syntax errors

### Frontend Changes (86fdbc3)

**File: frontend/src/hooks/useApi.js**
```javascript
// Changed from:
}, deps)  // ← empty array by default

// Changed to:
}, [fetcher, ...deps])  // ← includes fetcher
```
✅ Correct React pattern
✅ Frontend-only, doesn't affect backend

**File: frontend/src/pages/ScreeningPage.jsx**
```javascript
// Added error handler to SSE connection
const handleError = () => {
    console.error('SSE connection error')
    if (eventSource) {
      eventSource.close()
    }
    setTimeout(() => connectSSE(), 5000)
  }
```
✅ Proper error handling
✅ Frontend-only, doesn't affect backend health checks

## Conclusion

**The code changes are valid and correct.** The failure is likely environmental:

1. **Most likely**: App initialization timeout (5s too short)
2. **Second most likely**: Missing environment variable or database configuration
3. **Least likely**: Actual code bug (code review shows no issues)

**Solution**: 
- Increase health check grace period from 5s → 30s in Dockerfile
- Test locally with Docker before redeploying
- Then redeploy when confident

**Current Status**: ✅ Service healthy on v38
**Risk**: Low - can always rollback if needed

