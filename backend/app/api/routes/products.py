from typing import List
from fastapi import APIRouter, HTTPException, status
from app.schemas.product import ProductCreate, ProductUpdate, ProductInDB, ProductRecipe
from app.services.product_service import ProductService

router = APIRouter()

@router.post("", response_model=ProductInDB, status_code=status.HTTP_201_CREATED)
async def create_product(product_in: ProductCreate):
    try:
        return await ProductService.create_product(product_in)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

@router.get("", response_model=List[ProductInDB])
async def list_products():
    return await ProductService.list_products()

@router.get("/{id}", response_model=ProductInDB)
async def get_product(id: str):
    product = await ProductService.get_product_by_id(id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product

@router.put("/{id}", response_model=ProductInDB)
async def update_product(id: str, product_update: ProductUpdate):
    product = await ProductService.update_product(id, product_update)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product

@router.post("/{id}/recipes", response_model=ProductInDB)
async def add_or_update_recipe(id: str, recipe: ProductRecipe):
    try:
        product = await ProductService.add_or_update_recipe(id, recipe)
        if not product:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
        return product
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/{id}/recipes", response_model=List[ProductRecipe])
async def list_product_recipes(id: str):
    product = await ProductService.get_product_by_id(id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product.get("recipes", [])

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(id: str):
    deleted = await ProductService.delete_product(id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
