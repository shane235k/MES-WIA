from typing import List
from fastapi import APIRouter
from app.schemas.audit import AuditEventInDB
from app.core.database import get_db

router = APIRouter()

@router.get("", response_model=List[AuditEventInDB])
async def list_audit_events():
    """
    Retrieve the 100 most recent audit events logged in the system.
    """
    db = get_db()
    events = []
    async for doc in db.audit_events.find().sort("timestamp", -1).limit(100):
        events.append(doc)
    return events
