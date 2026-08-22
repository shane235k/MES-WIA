import pytest
from app.services.user_service import UserService
from app.core.database import get_db

@pytest.mark.asyncio
async def test_user_crud_and_audit():
    db = get_db()
    
    # 1. Create User
    user_data = {
        "employeeId": "EMP-101",
        "name": "Alice Smith",
        "email": "alice@mes.com",
        "role": "ADMIN",
        "department": "IT",
        "status": "ACTIVE"
    }
    
    from app.schemas.user import UserCreate
    created = await UserService.create_user(UserCreate(**user_data))
    assert created["employeeId"] == "EMP-101"
    user_id = str(created["_id"])
    
    # Verify Audit Event for creation
    audit = await db.audit_events.find_one({"action": "USER_CREATED", "entityId": user_id})
    assert audit is not None
    assert audit["metadata"]["employeeId"] == "EMP-101"

    # 2. Duplicate employeeId check
    with pytest.raises(ValueError) as exc:
        await UserService.create_user(UserCreate(**user_data))
    assert "already exists" in str(exc.value)

    # 3. Duplicate email check
    duplicate_email_user = user_data.copy()
    duplicate_email_user["employeeId"] = "EMP-102"
    with pytest.raises(ValueError) as exc:
        await UserService.create_user(UserCreate(**duplicate_email_user))
    assert "already exists" in str(exc.value)

    # 4. Get User
    fetched = await UserService.get_user_by_id(user_id)
    assert fetched is not None
    assert fetched["name"] == "Alice Smith"

    # 5. Update User
    from app.schemas.user import UserUpdate
    updated = await UserService.update_user(user_id, UserUpdate(name="Alice Johnson"))
    assert updated["name"] == "Alice Johnson"
    
    # Verify Audit Event for update
    audit_up = await db.audit_events.find_one({"action": "USER_UPDATED", "entityId": user_id})
    assert audit_up is not None

    # 6. Delete User
    deleted = await UserService.delete_user(user_id)
    assert deleted is True
    
    # Verify Audit Event for deletion
    audit_del = await db.audit_events.find_one({"action": "USER_DELETED", "entityId": user_id})
    assert audit_del is not None

    # Verify not found
    fetched_after = await UserService.get_user_by_id(user_id)
    assert fetched_after is None
