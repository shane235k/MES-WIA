import pytest
from bson import ObjectId
from app.services.capability_service import CapabilityService
from app.services.machine_service import MachineService
from app.schemas.capability import CapabilityCreate
from app.schemas.machine import MachineCreate, MachineUpdate, MACHINE_TYPE_COLORS

@pytest.mark.asyncio
async def test_machine_crud_color_and_rates():
    # 1. Create a valid capability first
    cap = await CapabilityService.create_capability(CapabilityCreate(
        code="CNC_MILLING",
        name="CNC Milling",
        description="Milling metals"
    ))
    cap_id = str(cap["_id"])

    # 2. Create Machine 1 (CUTTING type -> Blue)
    m1_data = {
        "machineCode": "M-TEST-01",
        "name": "Test Cutter 01",
        "type": "CUTTING",
        "capabilityIds": [cap_id],
        "location": "Fabrication Area",
        "availability": True,
        "processingRate": 2.5,
        "rateUnit": "units/sec"
    }
    m1 = await MachineService.create_machine(MachineCreate(**m1_data))
    assert m1["machineCode"] == "M-TEST-01"
    assert m1["color"] == MACHINE_TYPE_COLORS["CUTTING"]
    assert m1["processingRate"] == 2.5
    m1_id = str(m1["_id"])

    # 3. Create Machine 2 of same type (CUTTING) - must succeed and share type color
    m2_data = {
        "machineCode": "M-TEST-02",
        "name": "Test Cutter 02",
        "type": "CUTTING",
        "capabilityIds": [cap_id],
        "location": "Fabrication Area",
        "availability": True,
        "processingRate": 1.0,
        "rateUnit": "units/sec"
    }
    m2 = await MachineService.create_machine(MachineCreate(**m2_data))
    assert m2["machineCode"] == "M-TEST-02"
    assert m2["color"] == MACHINE_TYPE_COLORS["CUTTING"]
    m2_id = str(m2["_id"])

    # 4. Create Multi-Purpose Machine supporting CUTTING and BENDING
    m3_data = {
        "machineCode": "M-TEST-03",
        "name": "Hybrid Cell 1",
        "type": "MULTI_PURPOSE",
        "supportedTypes": ["CUTTING", "BENDING"],
        "capabilityIds": [cap_id],
        "location": "Cell Area",
        "availability": True,
        "processingRate": 1.5,
        "rateUnit": "units/sec"
    }
    m3 = await MachineService.create_machine(MachineCreate(**m3_data))
    assert m3["color"] == MACHINE_TYPE_COLORS["MULTI_PURPOSE"]
    m3_id = str(m3["_id"])

    # 5. Test compatible machines query (including multi-purpose)
    compat_cutting = await MachineService.find_compatible_machines(required_machine_type="CUTTING")
    compat_codes = [m["machineCode"] for m in compat_cutting]
    assert "M-TEST-01" in compat_codes
    assert "M-TEST-02" in compat_codes
    assert "M-TEST-03" in compat_codes

    # 6. Test maintenance scheduling
    maint = await MachineService.schedule_maintenance(
        machine_id=m1_id,
        duration_minutes=15,
        reason="Hydraulic overhaul"
    )
    assert maint["status"] == "MAINTENANCE"
    assert maint["maintenanceDurationMinutes"] == 15
    assert maint["maintenanceEstimatedEnd"] is not None

    # Clean up
    await MachineService.delete_machine(m1_id)
    await MachineService.delete_machine(m2_id)
    await MachineService.delete_machine(m3_id)
    await CapabilityService.delete_capability(cap_id)
