import json
import logging
from typing import Optional, Any
from app.core.redis import get_redis

logger = logging.getLogger(__name__)

class RedisService:
    """
    A service abstraction for Redis operations.
    Hides direct Redis client operations to allow simple transitions 
    or mock setups in the future.
    """
    
    @staticmethod
    async def set_key(key: str, value: Any, expire_seconds: Optional[int] = None) -> bool:
        """
        Store a key-value pair in Redis. Values are serialized to JSON if they are dicts/lists.
        """
        try:
            client = get_redis()
            if isinstance(value, (dict, list)):
                serialized_value = json.dumps(value)
            else:
                serialized_value = str(value)
                
            await client.set(key, serialized_value, ex=expire_seconds)
            return True
        except Exception as e:
            logger.error(f"Redis set_key failed for {key}: {e}")
            return False

    @staticmethod
    async def get_key(key: str) -> Optional[str]:
        """
        Retrieve raw string value from Redis.
        """
        try:
            client = get_redis()
            return await client.get(key)
        except Exception as e:
            logger.error(f"Redis get_key failed for {key}: {e}")
            return None

    @staticmethod
    async def get_json(key: str) -> Optional[Any]:
        """
        Retrieve and JSON-deserialize a value from Redis.
        """
        raw_val = await RedisService.get_key(key)
        if not raw_val:
            return None
        try:
            return json.loads(raw_val)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON for key {key}: {raw_val}")
            return raw_val

    @staticmethod
    async def delete_key(key: str) -> bool:
        """
        Delete a key from Redis.
        """
        try:
            client = get_redis()
            result = await client.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f"Redis delete_key failed for {key}: {e}")
            return False

    @staticmethod
    async def publish_event(channel: str, message: Any) -> int:
        """
        Publish an event to a Redis pub/sub channel.
        """
        try:
            client = get_redis()
            if isinstance(message, (dict, list)):
                payload = json.dumps(message)
            else:
                payload = str(message)
            receivers = await client.publish(channel, payload)
            return receivers
        except Exception as e:
            logger.error(f"Redis publish_event failed for channel {channel}: {e}")
            return 0

    @staticmethod
    async def enqueue_job(queue_name: str, payload: dict) -> bool:
        """
        Push a background job payload to the right of a list (FIFO queue).
        """
        try:
            client = get_redis()
            serialized_payload = json.dumps(payload)
            await client.rpush(queue_name, serialized_payload)
            return True
        except Exception as e:
            logger.error(f"Redis enqueue_job failed for queue {queue_name}: {e}")
            return False

    @staticmethod
    async def dequeue_job(queue_name: str) -> Optional[dict]:
        """
        Pop a background job payload from the left of a list (FIFO queue).
        """
        try:
            client = get_redis()
            raw_payload = await client.lpop(queue_name)
            if raw_payload:
                return json.loads(raw_payload)
            return None
        except Exception as e:
            logger.error(f"Redis dequeue_job failed for queue {queue_name}: {e}")
            return None

    @staticmethod
    async def acquire_lock(lock_key: str, ttl_seconds: int = 10) -> bool:
        """
        Acquire a distributed lock with TTL using Redis SET NX EX.
        Returns True if acquired, False if already held or on failure.
        """
        try:
            client = get_redis()
            res = await client.set(lock_key, "1", nx=True, ex=ttl_seconds)
            return bool(res)
        except Exception as e:
            logger.warning(f"Redis acquire_lock failed for {lock_key} (fallback enabled): {e}")
            return True

    @staticmethod
    async def release_lock(lock_key: str) -> bool:
        """
        Release distributed lock.
        """
        try:
            client = get_redis()
            res = await client.delete(lock_key)
            return bool(res)
        except Exception as e:
            logger.warning(f"Redis release_lock failed for {lock_key}: {e}")
            return False

