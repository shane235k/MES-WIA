from datetime import datetime
from bson import ObjectId
from typing import List, Optional
from app.core.database import get_db
from app.schemas.material_specification import MaterialSpecificationCreate, MaterialSpecificationUpdate
from app.services.audit_service import AuditService

class MaterialSpecificationService:
    @staticmethod
    async def create_specification(spec_in: MaterialSpecificationCreate, actor_id: str = "SYSTEM") -> dict:
        db = get_db()
        
        # Check duplicate specificationCode
        existing = await db.material_specifications.find_one({"specificationCode": spec_in.specificationCode})
        if existing:
            raise ValueError(f"Material specification with code '{spec_in.specificationCode}' already exists")
            
        spec_data = spec_in.model_dump()
        spec_data["createdAt"] = datetime.utcnow()
        spec_data["updatedAt"] = datetime.utcnow()
        
        result = await db.material_specifications.insert_one(spec_data)
        spec_data["_id"] = result.inserted_id
        
        await AuditService.log_event(
            actor_id=actor_id,
            actor_type="USER" if actor_id != "SYSTEM" else "SYSTEM",
            action="MATERIAL_SPECIFICATION_CREATED",
            entity_type="material_specification",
            entity_id=str(result.inserted_id),
            source="ADMIN",
            metadata={"specificationCode": spec_in.specificationCode, "name": spec_in.name, "category": spec_in.category.value if hasattr(spec_in.category, "value") else str(spec_in.category)}
        )
        return spec_data

    @staticmethod
    async def get_specification_by_id(spec_id: str) -> Optional[dict]:
        db = get_db()
        if not ObjectId.is_valid(spec_id):
            return None
        return await db.material_specifications.find_one({"_id": ObjectId(spec_id)})

    @staticmethod
    async def get_specification_by_code(spec_code: str) -> Optional[dict]:
        db = get_db()
        return await db.material_specifications.find_one({"specificationCode": spec_code})

    @staticmethod
    async def list_specifications(category: Optional[str] = None) -> List[dict]:
        db = get_db()
        query = {}
        if category:
            query["category"] = category
        specs = []
        async for doc in db.material_specifications.find(query):
            specs.append(doc)
        return specs

    @staticmethod
    async def update_specification(spec_id: str, spec_update: MaterialSpecificationUpdate, actor_id: str = "SYSTEM") -> Optional[dict]:
        db = get_db()
        if not ObjectId.is_valid(spec_id):
            return None
            
        update_data = spec_update.model_dump(exclude_unset=True)
        if not update_data:
            return await MaterialSpecificationService.get_specification_by_id(spec_id)
            
        update_data["updatedAt"] = datetime.utcnow()
        
        result = await db.material_specifications.find_one_and_update(
            {"_id": ObjectId(spec_id)},
            {"$set": update_data},
            return_document=True
        )
        if result:
            await AuditService.log_event(
                actor_id=actor_id,
                actor_type="USER" if actor_id != "SYSTEM" else "SYSTEM",
                action="MATERIAL_SPECIFICATION_UPDATED",
                entity_type="material_specification",
                entity_id=str(spec_id),
                source="ADMIN",
                metadata={"updated_fields": list(update_data.keys())}
            )
        return result

    @staticmethod
    async def delete_specification(spec_id: str, actor_id: str = "SYSTEM") -> bool:
        db = get_db()
        if not ObjectId.is_valid(spec_id):
            return False
            
        result = await db.material_specifications.delete_one({"_id": ObjectId(spec_id)})
        deleted = result.deleted_count > 0
        if deleted:
            await AuditService.log_event(
                actor_id=actor_id,
                actor_type="USER" if actor_id != "SYSTEM" else "SYSTEM",
                action="MATERIAL_SPECIFICATION_DELETED",
                entity_type="material_specification",
                entity_id=str(spec_id),
                source="ADMIN"
            )
        return deleted
