from datetime import datetime
from bson import ObjectId
from typing import List, Optional
from app.core.database import get_db
from app.schemas.capability import CapabilityCreate, CapabilityUpdate
from app.services.audit_service import AuditService

class CapabilityService:
    @staticmethod
    async def create_capability(capability_in: CapabilityCreate, actor_id: str = "SYSTEM") -> dict:
        db = get_db()
        
        # Check duplicate code
        existing = await db.capabilities.find_one({"code": capability_in.code})
        if existing:
            raise ValueError(f"Capability with code '{capability_in.code}' already exists")
            
        capability_data = capability_in.model_dump()
        capability_data["createdAt"] = datetime.utcnow()
        capability_data["updatedAt"] = datetime.utcnow()
        
        result = await db.capabilities.insert_one(capability_data)
        capability_data["_id"] = result.inserted_id
        
        await AuditService.log_event(
            actor_id=actor_id,
            actor_type="USER" if actor_id != "SYSTEM" else "SYSTEM",
            action="CAPABILITY_CREATED",
            entity_type="capability",
            entity_id=str(result.inserted_id),
            source="ADMIN",
            metadata={"code": capability_in.code, "name": capability_in.name}
        )
        return capability_data

    @staticmethod
    async def get_capability_by_id(cap_id: str) -> Optional[dict]:
        db = get_db()
        if not ObjectId.is_valid(cap_id):
            return None
        return await db.capabilities.find_one({"_id": ObjectId(cap_id)})

    @staticmethod
    async def get_capability_by_code(code: str) -> Optional[dict]:
        db = get_db()
        return await db.capabilities.find_one({"code": code})

    @staticmethod
    async def list_capabilities() -> List[dict]:
        db = get_db()
        capabilities = []
        async for doc in db.capabilities.find():
            capabilities.append(doc)
        return capabilities

    @staticmethod
    async def update_capability(cap_id: str, capability_update: CapabilityUpdate, actor_id: str = "SYSTEM") -> Optional[dict]:
        db = get_db()
        if not ObjectId.is_valid(cap_id):
            return None
            
        update_data = capability_update.model_dump(exclude_unset=True)
        if not update_data:
            return await CapabilityService.get_capability_by_id(cap_id)
            
        update_data["updatedAt"] = datetime.utcnow()
        
        result = await db.capabilities.find_one_and_update(
            {"_id": ObjectId(cap_id)},
            {"$set": update_data},
            return_document=True
        )
        if result:
            await AuditService.log_event(
                actor_id=actor_id,
                actor_type="USER" if actor_id != "SYSTEM" else "SYSTEM",
                action="CAPABILITY_UPDATED",
                entity_type="capability",
                entity_id=str(cap_id),
                source="ADMIN",
                metadata={"updated_fields": list(update_data.keys())}
            )
        return result

    @staticmethod
    async def delete_capability(cap_id: str, actor_id: str = "SYSTEM") -> bool:
        db = get_db()
        if not ObjectId.is_valid(cap_id):
            return False
            
        result = await db.capabilities.delete_one({"_id": ObjectId(cap_id)})
        deleted = result.deleted_count > 0
        if deleted:
            await AuditService.log_event(
                actor_id=actor_id,
                actor_type="USER" if actor_id != "SYSTEM" else "SYSTEM",
                action="CAPABILITY_DELETED",
                entity_type="capability",
                entity_id=str(cap_id),
                source="ADMIN"
            )
        return deleted
