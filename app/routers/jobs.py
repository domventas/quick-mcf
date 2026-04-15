"""
Job monitoring routes — /api/v1/jobs
"""

from fastapi import APIRouter, Depends
from app.services.auth import validate_api_key
from app.schemas import JobStatusResponse
from app.jobs import scheduler

router = APIRouter(prefix="/api/v1/jobs", tags=["Jobs"], dependencies=[Depends(validate_api_key)])

@router.get("", response_model=list[JobStatusResponse], include_in_schema=False)
async def get_jobs_status():
    """
    Get status of background jobs directly from the scheduler instance.
    """
    job_statuses = []
    
    if not scheduler.running:
        return []

    for job in scheduler.get_jobs():
        job_statuses.append({
            "job_name": job.id,
            "next_run": job.next_run_time,
            "status": "active" if job.next_run_time else "paused"
        })
        
    return job_statuses
