import time
import logging
from typing import Optional
import redis.asyncio as aioredis
from app.core.config import settings

logger = logging.getLogger(__name__)

class RedisManager:
    def __init__(self):
        self.client: Optional[aioredis.Redis] = None

    async def connect(self) -> None:
        """
        Establish connection to Redis using the settings environment URL.
        """
        logger.info(f"Connecting to Redis at {settings.REDIS_HOST}:{settings.REDIS_PORT}")
        try:
            self.client = aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_timeout=2.0,  # 2 seconds connection timeout
                socket_connect_timeout=2.0
            )
            # Verify connectivity
            await self.client.ping()
            logger.info("Successfully connected to Redis")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    async def disconnect(self) -> None:
        """
        Close Redis connection client.
        """
        if self.client:
            logger.info("Closing Redis connection")
            await self.client.close()
            self.client = None
            logger.info("Redis connection closed")

    async def ping_redis(self) -> float:
        """
        Measures the latency of pinging the Redis server.
        Returns the duration in milliseconds.
        Raises an exception if the client is not initialized or Redis is unreachable.
        """
        if not self.client:
            raise ConnectionError("Redis client is not connected")
        
        start_time = time.perf_counter()
        await self.client.ping()
        end_time = time.perf_counter()
        
        latency_ms = (end_time - start_time) * 1000
        return round(latency_ms, 2)

# Global redis manager instance
redis_manager = RedisManager()

def get_redis() -> aioredis.Redis:
    """
    Dependency or helper to access the Redis client instance.
    """
    if redis_manager.client is None:
        raise RuntimeError("Redis not initialized")
    return redis_manager.client
