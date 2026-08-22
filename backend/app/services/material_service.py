from datetime import datetime
from bson import ObjectId
from typing import List, Optional
from app.core.database import get_db
from app.schemas.material import MaterialCreate, MaterialUpdate
from app.services.audit_service import AuditService

class MaterialService:
    @staticmethod
    async def create_material(material_in: MaterialCreate, actor_id: str = "SYSTEM") -> dict:
        db = get_db()
        
        # Check duplicate materialCode
        existing = await db.materials.find_one({"materialCode": material_in.materialCode})
        if existing:
            raise ValueError(f"Material with code '{material_in.materialCode}' already exists")
            
        material_data = material_in.model_dump()
        material_data["createdAt"] = datetime.utcnow()
        material_data["updatedAt"] = datetime.utcnow()
        
        result = await db.materials.insert_one(material_data)
        material_data["_id"] = result.inserted_id
        
        await AuditService.log_event(
            actor_id=actor_id,
            actor_type="USER" if actor_id != "SYSTEM" else "SYSTEM",
            action="MATERIAL_CREATED",
            entity_type="material",
            entity_id=str(result.inserted_id),
            source="ADMIN",
            metadata={"materialCode": material_in.materialCode, "name": material_in.name}
        )
        return material_data

    @staticmethod
    async def get_material_by_id(material_id: str) -> Optional[dict]:
        db = get_db()
        if not ObjectId.is_valid(material_id):
            return None
        return await db.materials.find_one({"_id": ObjectId(material_id)})

    @staticmethod
    async def list_materials() -> List[dict]:
        db = get_db()
        materials = []
        async for doc in db.materials.find():
            materials.append(doc)
        return materials

    @staticmethod
    async def update_material(material_id: str, material_update: MaterialUpdate, actor_id: str = "SYSTEM") -> Optional[dict]:
        db = get_db()
        if not ObjectId.is_valid(material_id):
            return None
            
        update_data = material_update.model_dump(exclude_unset=True)
        if not update_data:
            return await MaterialService.get_material_by_id(material_id)
            
        update_data["updatedAt"] = datetime.utcnow()
        
        result = await db.materials.find_one_and_update(
            {"_id": ObjectId(material_id)},
            {"$set": update_data},
            return_document=True
        )
        if result:
            await AuditService.log_event(
                actor_id=actor_id,
                actor_type="USER" if actor_id != "SYSTEM" else "SYSTEM",
                action="MATERIAL_UPDATED",
                entity_type="material",
                entity_id=str(material_id),
                source="ADMIN",
                metadata={"updated_fields": list(update_data.keys())}
            )
        return result

    @staticmethod
    async def delete_material(material_id: str, actor_id: str = "SYSTEM") -> bool:
        db = get_db()
        if not ObjectId.is_valid(material_id):
            return False
            
        result = await db.materials.delete_one({"_id": ObjectId(material_id)})
        deleted = result.deleted_count > 0
        if deleted:
            await AuditService.log_event(
                actor_id=actor_id,
                actor_type="USER" if actor_id != "SYSTEM" else "SYSTEM",
                action="MATERIAL_DELETED",
                entity_type="material",
                entity_id=str(material_id),
                source="ADMIN"
            )
        return deleted
