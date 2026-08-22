import time
import logging
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.db = None

    async def connect(self) -> None:
        """
        Establish MongoDB connection client using environment variables.
        """
        logger.info(f"Connecting to MongoDB at {settings.MONGODB_HOST}:{settings.MONGODB_PORT}")
        try:
            self.client = AsyncIOMotorClient(
                settings.mongodb_uri,
                serverSelectionTimeoutMS=2000  # Fail fast (2 seconds timeout) if unreachable
            )
            # Accessing the database will initialize it, motor initializes lazily but we can verify below
            self.db = self.client[settings.MONGODB_DATABASE]
            
            # Verify connectivity immediately by running a ping command
            await self.client.admin.command("ping")
            logger.info("Successfully connected to MongoDB")
            
            # Ensure indexes are created
            await self.create_indexes()
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise

    async def create_indexes(self) -> None:
        """
        Create unique and lookup indexes for all collections.
        """
        if self.db is None:
            raise RuntimeError("Database not initialized")
        
        logger.info("Ensuring database indexes...")
        try:
            # users
            await self.db.users.create_index("employeeId", unique=True)
            await self.db.users.create_index("email", unique=True)
            
            # capabilities
            await self.db.capabilities.create_index("code", unique=True)
            
            # machines
            await self.db.machines.create_index("machineCode", unique=True)
            
            # products
            await self.db.products.create_index("productCode", unique=True)
            
            # materials
            await self.db.materials.create_index("materialCode", unique=True)
            await self.db.materials.create_index("specificationId")
            
            # material_specifications
            await self.db.material_specifications.create_index("specificationCode", unique=True)
            await self.db.material_specifications.create_index("category")
            
            # inventory_lots
            await self.db.inventory_lots.create_index([("lotNumber", 1), ("materialId", 1)], unique=True)
            await self.db.inventory_lots.create_index("materialId")
            await self.db.inventory_lots.create_index("specificationId")
            await self.db.inventory_lots.create_index("status")
            await self.db.inventory_lots.create_index("expiryDate")
            
            # material_reservations
            await self.db.material_reservations.create_index("workOrderId")
            await self.db.material_reservations.create_index([("workOrderId", 1), ("operationId", 1)])
            await self.db.material_reservations.create_index("lotId")
            await self.db.material_reservations.create_index("materialId")
            await self.db.material_reservations.create_index("status")
            
            # material_transactions
            await self.db.material_transactions.create_index("transactionId", unique=True)
            await self.db.material_transactions.create_index("materialId")
            await self.db.material_transactions.create_index("lotId")
            await self.db.material_transactions.create_index("workOrderId")
            await self.db.material_transactions.create_index("operationId")
            await self.db.material_transactions.create_index("timestamp")
            
            # workflows
            await self.db.workflows.create_index([("workflowCode", 1), ("version", 1)], unique=True)
            await self.db.workflows.create_index("productId")
            
            # work_orders
            await self.db.work_orders.create_index("workOrderCode", unique=True)
            await self.db.work_orders.create_index("productId")
            await self.db.work_orders.create_index("workflowId")
            
            # audit_events
            await self.db.audit_events.create_index("timestamp")
            await self.db.audit_events.create_index([("entityType", 1), ("entityId", 1)])
            
            # executions
            await self.db.executions.create_index("workOrderId", unique=True)
            await self.db.executions.create_index("status")
            
            # execution_events
            await self.db.execution_events.create_index([("executionId", 1), ("timestamp", 1)])
            await self.db.execution_events.create_index([("workOrderId", 1), ("timestamp", 1)])
            await self.db.execution_events.create_index([("operationId", 1), ("timestamp", 1)])
            await self.db.execution_events.create_index([("machineId", 1), ("timestamp", 1)])
            
            # ai_operations
            await self.db.ai_operations.create_index("operationId", unique=True)
            await self.db.ai_operations.create_index("incidentId")
            await self.db.ai_operations.create_index("status")
            await self.db.ai_operations.create_index("createdAt")
            
            logger.info("Database indexes ensured successfully")
        except Exception as e:
            logger.error(f"Failed to create database indexes: {e}")
            raise

    async def disconnect(self) -> None:
        """
        Close MongoDB connection client.
        """
        if self.client:
            logger.info("Closing MongoDB connection")
            self.client.close()
            self.client = None
            self.db = None
            logger.info("MongoDB connection closed")

    async def ping_db(self) -> float:
        """
        Measures the latency of pinging the MongoDB server.
        Returns the duration in milliseconds.
        Raises an exception if the client is not initialized or database is unreachable.
        """
        if not self.client:
            raise ConnectionError("MongoDB client is not connected")
        
        start_time = time.perf_counter()
        # Run database ping command
        await self.client.admin.command("ping")
        end_time = time.perf_counter()
        
        latency_ms = (end_time - start_time) * 1000
        return round(latency_ms, 2)

# Global database manager instance
db_manager = DatabaseManager()

def get_db():
    """
    Dependency or helper to access the database instance.
    """
    if db_manager.db is None:
        raise RuntimeError("Database not initialized")
    return db_manager.db
