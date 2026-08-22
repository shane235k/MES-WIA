from typing import Optional
from pydantic import BaseModel

class ServiceHealthStatus(BaseModel):
    status: str  # "healthy" or "unreachable"
    latency_ms: Optional[float] = None
    error: Optional[str] = None

class APIHealthStatus(BaseModel):
    status: str  # "healthy"

class HealthCheckResponse(BaseModel):
    status: str  # "healthy" or "degraded"
    api: APIHealthStatus
    database: ServiceHealthStatus
    redis: ServiceHealthStatus
