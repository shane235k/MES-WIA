from datetime import datetime
from app.core.database import get_db

class AuditService:
    @staticmethod
    async def log_event(
        actor_id: str,
        actor_type: str,
        action: str,
        entity_type: str,
        entity_id: str,
        source: str,
        metadata: dict = None
    ) -> None:
        """
        Asynchronously write an audit event into the MongoDB log collection.
        Does not raise errors to ensure that audit failures do not block business operations.
        """
        try:
            db = get_db()
            event = {
                "timestamp": datetime.utcnow(),
                "actorId": actor_id,
                "actorType": actor_type,
                "action": action,
                "entityType": entity_type,
                "entityId": str(entity_id),
                "source": source,
                "metadata": metadata or {},
                "createdAt": datetime.utcnow()
            }
            await db.audit_events.insert_one(event)
        except Exception as e:
            # Log the error but do not raise, ensuring audit issues are non-blocking
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to write audit event: {e}")
