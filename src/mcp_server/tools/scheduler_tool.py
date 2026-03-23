"""
MCP Tool: scheduler.run_daily / scheduler.run_weekly
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel

from src.mcp_server.middleware.error_handler import tool_endpoint

router = APIRouter()

# In-memory job registry (in production, use Celery/Prefect/APScheduler)
_jobs: dict[str, dict] = {}


class DailyJobRequest(BaseModel):
    job_name: str
    params: dict | None = None


class WeeklyJobRequest(BaseModel):
    job_name: str
    params: dict | None = None
    day_of_week: str = "monday"


@router.post("/run_daily")
@tool_endpoint
async def run_daily(req: DailyJobRequest):
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "job_name": req.job_name,
        "schedule": "daily",
        "params": req.params,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "scheduled",
    }

    # In production, this would enqueue via Celery:
    # celery_app.send_task(f"jobs.{req.job_name}", kwargs=req.params)

    return {"job_id": job_id, "scheduled_at": _jobs[job_id]["created_at"]}


@router.post("/run_weekly")
@tool_endpoint
async def run_weekly(req: WeeklyJobRequest):
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "job_name": req.job_name,
        "schedule": f"weekly:{req.day_of_week}",
        "params": req.params,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "scheduled",
    }
    return {
        "job_id": job_id,
        "scheduled_at": _jobs[job_id]["created_at"],
        "day_of_week": req.day_of_week,
    }


@router.get("/jobs")
async def list_jobs():
    return {"jobs": _jobs}
