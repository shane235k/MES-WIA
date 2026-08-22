import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.database import db_manager
from app.core.redis import redis_manager
from app.services.execution_engine import ExecutionEngine
from app.api.routes import (
    health, users, capabilities, machines, products, materials, workflows, work_orders, audit_events, ws,
    incidents, operator_alerts, operator_activations, operator_context, ai_operations, inventory, ai_work_orders,
    predictive_maintenance
)

# Set up logging
setup_logging()
logger = logging.getLogger(__name__)

async def background_execution_loop():
    """
    Background asynchronous task that ticks every second to evaluate running work orders.
    """
    logger.info("Background execution engine loop initialized.")
    try:
        while True:
            await asyncio.sleep(1)
            await ExecutionEngine.run_execution_loop_tick()
    except asyncio.CancelledError:
        logger.info("Background execution engine loop cancelled.")
    except Exception as e:
        logger.error(f"Error in background execution engine loop: {e}", exc_info=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI Lifespan events hook.
    Initializes external services (MongoDB, Redis) on startup.
    Spawns background execution loop.
    Fails startup clearly if services are unreachable.
    Cleans up connections on shutdown.
    """
    logger.info("Initializing application services...")
    
    # 1. Connect to MongoDB
    try:
        await db_manager.connect()
    except Exception as e:
        logger.critical(f"Required infrastructure MongoDB is unavailable: {e}")
        raise RuntimeError("MongoDB connection failed at startup") from e
        
    # 2. Connect to Redis
    try:
        await redis_manager.connect()
    except Exception as e:
        logger.critical(f"Required infrastructure Redis is unavailable: {e}")
        await db_manager.disconnect()
        raise RuntimeError("Redis connection failed at startup") from e
        
    logger.info("All application services started successfully.")
    
    # 3. Spawn background execution engine loop
    engine_task = asyncio.create_task(background_execution_loop())
    
    yield
    
    logger.info("Stopping application services...")
    engine_task.cancel()
    try:
        await engine_task
    except asyncio.CancelledError:
        pass
        
    await db_manager.disconnect()
    await redis_manager.disconnect()
    logger.info("Application services stopped.")

# Initialize app
app = FastAPI(
    title="Adaptive MES API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "tauri://localhost",
        "http://tauri.localhost",
        "https://tauri.localhost",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root fallback route
@app.get("/")
async def root():
    return {
        "message": "Adaptive MES Backend API is operational. Visit /api/health for system status."
    }

# Register routers
app.include_router(health.router, prefix="/api")
app.include_router(ws.router, prefix="/api")
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(capabilities.router, prefix="/api/capabilities", tags=["Capabilities"])
app.include_router(machines.router, prefix="/api/machines", tags=["Machines"])
app.include_router(products.router, prefix="/api/products", tags=["Products"])
app.include_router(inventory.router, prefix="/api", tags=["Inventory & Materials"])
app.include_router(materials.router, prefix="/api/materials", tags=["Materials"])
app.include_router(workflows.router, prefix="/api/workflows", tags=["Workflows"])
app.include_router(work_orders.router, prefix="/api/work-orders", tags=["Work Orders"])
app.include_router(audit_events.router, prefix="/api/audit-events", tags=["Audit Events"])
app.include_router(incidents.router, prefix="/api/incidents", tags=["Incidents"])
app.include_router(operator_alerts.router, prefix="/api/operator-alerts", tags=["Operator Alerts"])
app.include_router(operator_activations.router, tags=["Operator Activations"])
app.include_router(operator_context.router, tags=["Operator Context"])
app.include_router(ai_operations.router)
app.include_router(ai_work_orders.router)
app.include_router(predictive_maintenance.router, prefix="/api/predictive-maintenance", tags=["Predictive Maintenance"])

# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        f"Unhandled exception during request {request.method} {request.url}: {exc}", 
        exc_info=True,
        extra={"extra_fields": {"path": request.url.path, "method": request.method}}
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred."}
    )
