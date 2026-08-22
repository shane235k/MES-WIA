import pytest
from app.services.capability_service import CapabilityService
from app.schemas.capability import CapabilityCreate, CapabilityUpdate

@pytest.mark.asyncio
async def test_capability_crud():
    # 1. Create Capability
    cap_data = {
        "code": "WELDING",
        "name": "TIG Welding",
        "description": "Manual TIG welding station"
    }
    created = await CapabilityService.create_capability(CapabilityCreate(**cap_data))
    assert created["code"] == "WELDING"
    cap_id = str(created["_id"])

    # 2. Duplicate code constraint
    with pytest.raises(ValueError) as exc:
        await CapabilityService.create_capability(CapabilityCreate(**cap_data))
    assert "already exists" in str(exc.value)

    # 3. Get Capability
    fetched = await CapabilityService.get_capability_by_id(cap_id)
    assert fetched is not None
    assert fetched["name"] == "TIG Welding"

    # 4. List Capabilities
    lst = await CapabilityService.list_capabilities()
    assert len(lst) >= 1

    # 5. Update Capability
    updated = await CapabilityService.update_capability(cap_id, CapabilityUpdate(name="Advanced TIG Welding"))
    assert updated["name"] == "Advanced TIG Welding"

    # 6. Delete Capability
    deleted = await CapabilityService.delete_capability(cap_id)
    assert deleted is True
