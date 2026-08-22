from datetime import datetime
from bson import ObjectId
from typing import List, Optional
from app.core.database import get_db
from app.schemas.user import UserCreate, UserUpdate, UserRole, OperatorAvailability, UserStatus
from app.services.audit_service import AuditService

class UserService:
    @staticmethod
    async def create_user(user_in: UserCreate, actor_id: str = "SYSTEM") -> dict:
        db = get_db()
        
        # Check duplicate employeeId
        existing = await db.users.find_one({"employeeId": user_in.employeeId})
        if existing:
            raise ValueError(f"User with employeeId '{user_in.employeeId}' already exists")
            
        # Check duplicate email
        existing_email = await db.users.find_one({"email": user_in.email})
        if existing_email:
            raise ValueError(f"User with email '{user_in.email}' already exists")
            
        user_data = user_in.model_dump()
        user_data["createdAt"] = datetime.utcnow()
        user_data["updatedAt"] = datetime.utcnow()
        
        result = await db.users.insert_one(user_data)
        user_data["_id"] = result.inserted_id
        
        await AuditService.log_event(
            actor_id=actor_id,
            actor_type="USER" if actor_id != "SYSTEM" else "SYSTEM",
            action="USER_CREATED",
            entity_type="user",
            entity_id=str(result.inserted_id),
            source="ADMIN",
            metadata={"employeeId": user_in.employeeId, "email": user_in.email}
        )
        return user_data

    @staticmethod
    async def _enrich_user_work_order(doc: dict, db) -> dict:
        d = dict(doc)
        wo_id = d.get("currentWorkOrderId")
        op_identifiers = [str(d.get("_id", ""))]
        if d.get("employeeId"):
            op_identifiers.append(d["employeeId"])

        wo = None
        if wo_id and ObjectId.is_valid(wo_id):
            wo = await db.work_orders.find_one({"_id": ObjectId(wo_id)})
            if not wo or wo.get("status") not in ["IN_PROGRESS", "PENDING"]:
                wo = None
                d["currentWorkOrderId"] = None
                d["currentOperationId"] = None

        if not wo:
            wo = await db.work_orders.find_one({
                "status": "IN_PROGRESS",
                "operations.assignedOperatorId": {"$in": op_identifiers}
            })
            if wo:
                active_op = next(
                    (o for o in wo.get("operations", []) if o.get("assignedOperatorId") in op_identifiers and o.get("status") in ["IN_PROGRESS", "WAITING_FOR_RESOURCE", "READY", "INTERRUPTED"]),
                    None
                )
                if active_op:
                    d["currentWorkOrderId"] = str(wo["_id"])
                    d["currentOperationId"] = active_op.get("operationId")
                    d["availabilityStatus"] = OperatorAvailability.ASSIGNED.value

        if wo:
            d["currentWorkOrderCode"] = wo.get("workOrderCode")
            d["currentWorkOrderName"] = wo.get("name")
        else:
            d["currentWorkOrderCode"] = None
            d["currentWorkOrderName"] = None

        return d

    @staticmethod
    async def get_user_by_id(user_id: str) -> Optional[dict]:
        db = get_db()
        if not ObjectId.is_valid(user_id):
            return None
        doc = await db.users.find_one({"_id": ObjectId(user_id)})
        return await UserService._enrich_user_work_order(doc, db) if doc else None

    @staticmethod
    async def list_users() -> List[dict]:
        db = get_db()
        users = []
        async for doc in db.users.find():
            enriched = await UserService._enrich_user_work_order(doc, db)
            users.append(enriched)
        return users

    @staticmethod
    async def list_operators(only_available: bool = False) -> List[dict]:
        """
        List active operators, optionally filtered to only currently available operators.
        """
        db = get_db()
        query = {"role": UserRole.OPERATOR.value, "status": UserStatus.ACTIVE.value}
        if only_available:
            query["availabilityStatus"] = OperatorAvailability.AVAILABLE.value
            
        operators = []
        async for doc in db.users.find(query):
            operators.append(doc)
        return operators

    @staticmethod
    async def list_supervisors() -> List[dict]:
        """
        List users eligible for supervisor assignment (SUPERVISOR or ADMIN).
        """
        db = get_db()
        query = {
            "role": {"$in": [UserRole.SUPERVISOR.value, UserRole.ADMIN.value]},
            "status": UserStatus.ACTIVE.value
        }
        supervisors = []
        async for doc in db.users.find(query):
            supervisors.append(doc)
        return supervisors

    @staticmethod
    async def update_user(user_id: str, user_update: UserUpdate, actor_id: str = "SYSTEM") -> Optional[dict]:
        db = get_db()
        if not ObjectId.is_valid(user_id):
            return None
            
        update_data = user_update.model_dump(exclude_unset=True)
        if not update_data:
            return await UserService.get_user_by_id(user_id)
            
        # Check email duplicate if updating email
        if "email" in update_data:
            existing = await db.users.find_one({"email": update_data["email"], "_id": {"$ne": ObjectId(user_id)}})
            if existing:
                raise ValueError(f"User with email '{update_data['email']}' already exists")
                
        update_data["updatedAt"] = datetime.utcnow()
        
        result = await db.users.find_one_and_update(
            {"_id": ObjectId(user_id)},
            {"$set": update_data},
            return_document=True
        )
        if result:
            await AuditService.log_event(
                actor_id=actor_id,
                actor_type="USER" if actor_id != "SYSTEM" else "SYSTEM",
                action="USER_UPDATED",
                entity_type="user",
                entity_id=str(user_id),
                source="ADMIN",
                metadata={"updated_fields": list(update_data.keys())}
            )
        return result

    @staticmethod
    async def delete_user(user_id: str, actor_id: str = "SYSTEM") -> bool:
        db = get_db()
        if not ObjectId.is_valid(user_id):
            return False
            
        result = await db.users.delete_one({"_id": ObjectId(user_id)})
        deleted = result.deleted_count > 0
        if deleted:
            await AuditService.log_event(
                actor_id=actor_id,
                actor_type="USER" if actor_id != "SYSTEM" else "SYSTEM",
                action="USER_DELETED",
                entity_type="user",
                entity_id=str(user_id),
                source="ADMIN"
            )
        return deleted
