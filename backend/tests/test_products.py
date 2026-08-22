import pytest
from app.services.product_service import ProductService
from app.schemas.product import ProductCreate, ProductUpdate

@pytest.mark.asyncio
async def test_product_crud():
    # 1. Create Product
    prod_data = {
        "productCode": "WIDGET-X",
        "name": "Widget X",
        "description": "Standard high-durability Widget X",
        "unit": "pcs",
        "active": True
    }
    created = await ProductService.create_product(ProductCreate(**prod_data))
    assert created["productCode"] == "WIDGET-X"
    prod_id = str(created["_id"])

    # 2. Duplicate productCode constraint
    with pytest.raises(ValueError) as exc:
        await ProductService.create_product(ProductCreate(**prod_data))
    assert "already exists" in str(exc.value)

    # 3. Get Product
    fetched = await ProductService.get_product_by_id(prod_id)
    assert fetched is not None
    assert fetched["name"] == "Widget X"

    # 4. List Products
    lst = await ProductService.list_products()
    assert len(lst) >= 1

    # 5. Update Product
    updated = await ProductService.update_product(prod_id, ProductUpdate(name="Widget X-Max"))
    assert updated["name"] == "Widget X-Max"

    # 6. Delete Product
    deleted = await ProductService.delete_product(prod_id)
    assert deleted is True
