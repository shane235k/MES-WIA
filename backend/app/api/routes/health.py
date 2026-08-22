import asyncio
import logging
from fastapi import APIRouter
from app.schemas.health import HealthCheckResponse, ServiceHealthStatus, APIHealthStatus
from app.core.database import db_manager
from app.core.redis import redis_manager

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/health", response_model=HealthCheckResponse)
async def check_health():
    """
    Perform a complete asynchronous system health check.
    Queries MongoDB and Redis concurrently, measuring latency.
    If any database or cache is degraded/offline, reports 'degraded' overall status.
    """
    db_task = db_manager.ping_db()
    redis_task = redis_manager.ping_redis()
    
    # Run tests concurrently using gather with return_exceptions=True
    # to prevent one database crash from blocking the entire response.
    results = await asyncio.gather(db_task, redis_task, return_exceptions=True)
    
    db_result = results[0]
    redis_result = results[1]
    
    # Analyze Database Health
    if isinstance(db_result, Exception):
        logger.warning(f"Healthcheck MongoDB ping failed: {db_result}")
        db_status = ServiceHealthStatus(
            status="unreachable",
            error=str(db_result)
        )
    else:
        db_status = ServiceHealthStatus(
            status="healthy",
            latency_ms=db_result
        )
        
    # Analyze Redis Health
    if isinstance(redis_result, Exception):
        logger.warning(f"Healthcheck Redis ping failed: {redis_result}")
        redis_status = ServiceHealthStatus(
            status="unreachable",
            error=str(redis_result)
        )
    else:
        redis_status = ServiceHealthStatus(
            status="healthy",
            latency_ms=redis_result
        )
        
    # Determine overall status
    is_healthy = (db_status.status == "healthy") and (redis_status.status == "healthy")
    overall_status = "healthy" if is_healthy else "degraded"
    
    return HealthCheckResponse(
        status=overall_status,
        api=APIHealthStatus(status="healthy"),
        database=db_status,
        redis=redis_status
    )
