import pytest
from app.services.product_service import ProductService
from app.schemas.product import ProductCreate, ProductRecipe, RecipeStep

@pytest.mark.asyncio
async def test_product_recipe_crud_and_isolation():
    # 1. Create Product with initial Recipe
    step1 = RecipeStep(
        stepId="STEP-10",
        sequence=10,
        name="Laser Cutting",
        requiredCapabilityIds=[],
        requiredMachineType="CUTTING",
        estimatedQuantityRate=2.0,
        unit="pcs",
        dependencies=[]
    )
    recipe1 = ProductRecipe(
        recipeId="RECIPE-PART-A-V1",
        recipeName="PART-A:v1",
        version=1,
        status="ACTIVE",
        steps=[step1]
    )
    
    prod = await ProductService.create_product(ProductCreate(
        productCode="PART-A",
        name="Industrial Part A",
        description="Standard part",
        unit="pcs",
        recipes=[recipe1]
    ))
    prod_id = str(prod["_id"])
    assert len(prod["recipes"]) == 1
    assert prod["recipes"][0]["recipeId"] == "RECIPE-PART-A-V1"

    # 2. Add New Recipe Version
    step2 = RecipeStep(
        stepId="STEP-20",
        sequence=20,
        name="Press Brake Bending",
        requiredCapabilityIds=[],
        requiredMachineType="BENDING",
        estimatedQuantityRate=1.5,
        unit="pcs",
        dependencies=["STEP-10"]
    )
    recipe2 = ProductRecipe(
        recipeId="RECIPE-PART-A-V2",
        recipeName="PART-A:v2",
        version=2,
        status="DRAFT",
        steps=[step1, step2]
    )
    
    updated = await ProductService.add_or_update_recipe(prod_id, recipe2)
    assert len(updated["recipes"]) == 2
    
    # 3. Retrieve specific recipe
    fetched_r2 = await ProductService.get_recipe(prod_id, "RECIPE-PART-A-V2")
    assert fetched_r2 is not None
    assert fetched_r2["version"] == 2
    assert len(fetched_r2["steps"]) == 2

    # Clean up
    await ProductService.delete_product(prod_id)
