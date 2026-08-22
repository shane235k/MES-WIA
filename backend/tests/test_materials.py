import pytest
from app.services.material_service import MaterialService
from app.schemas.material import MaterialCreate, MaterialUpdate

@pytest.mark.asyncio
async def test_material_crud():
    # 1. Create Material
    mat_data = {
        "materialCode": "RAW-ALUM-3MM",
        "name": "3mm Aluminium Sheet",
        "unit": "sheets",
        "quantityAvailable": 100.0,
        "reorderLevel": 10.0,
        "active": True
    }
    created = await MaterialService.create_material(MaterialCreate(**mat_data))
    assert created["materialCode"] == "RAW-ALUM-3MM"
    mat_id = str(created["_id"])

    # 2. Duplicate materialCode constraint
    with pytest.raises(ValueError) as exc:
        await MaterialService.create_material(MaterialCreate(**mat_data))
    assert "already exists" in str(exc.value)

    # 3. Get Material
    fetched = await MaterialService.get_material_by_id(mat_id)
    assert fetched is not None
    assert fetched["name"] == "3mm Aluminium Sheet"

    # 4. List Materials
    lst = await MaterialService.list_materials()
    assert len(lst) >= 1

    # 5. Update Material
    updated = await MaterialService.update_material(mat_id, MaterialUpdate(quantityAvailable=150.0))
    assert updated["quantityAvailable"] == 150.0

    # 6. Delete Material
    deleted = await MaterialService.delete_material(mat_id)
    assert deleted is True
