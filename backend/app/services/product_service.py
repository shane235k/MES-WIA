from datetime import datetime
from bson import ObjectId
from typing import List, Optional
from app.core.database import get_db
from app.schemas.product import ProductCreate, ProductUpdate, ProductRecipe
from app.services.audit_service import AuditService

class ProductService:
    @staticmethod
    async def create_product(product_in: ProductCreate, actor_id: str = "SYSTEM") -> dict:
        db = get_db()
        
        # Check duplicate productCode
        existing = await db.products.find_one({"productCode": product_in.productCode})
        if existing:
            raise ValueError(f"Product with code '{product_in.productCode}' already exists")
            
        product_data = product_in.model_dump()
        product_data["createdAt"] = datetime.utcnow()
        product_data["updatedAt"] = datetime.utcnow()
        
        result = await db.products.insert_one(product_data)
        product_data["_id"] = result.inserted_id
        
        await AuditService.log_event(
            actor_id=actor_id,
            actor_type="USER" if actor_id != "SYSTEM" else "SYSTEM",
            action="PRODUCT_CREATED",
            entity_type="product",
            entity_id=str(result.inserted_id),
            source="ADMIN",
            metadata={"productCode": product_in.productCode, "name": product_in.name}
        )
        return product_data

    @staticmethod
    async def get_product_by_id(product_id: str) -> Optional[dict]:
        db = get_db()
        if not ObjectId.is_valid(product_id):
            return None
        return await db.products.find_one({"_id": ObjectId(product_id)})

    @staticmethod
    async def get_product_by_code(product_code: str) -> Optional[dict]:
        db = get_db()
        return await db.products.find_one({"productCode": product_code})

    @staticmethod
    async def list_products() -> List[dict]:
        db = get_db()
        products = []
        async for doc in db.products.find():
            products.append(doc)
        return products

    @staticmethod
    async def update_product(product_id: str, product_update: ProductUpdate, actor_id: str = "SYSTEM") -> Optional[dict]:
        db = get_db()
        if not ObjectId.is_valid(product_id):
            return None
            
        update_data = product_update.model_dump(exclude_unset=True)
        if not update_data:
            return await ProductService.get_product_by_id(product_id)
            
        update_data["updatedAt"] = datetime.utcnow()
        
        result = await db.products.find_one_and_update(
            {"_id": ObjectId(product_id)},
            {"$set": update_data},
            return_document=True
        )
        if result:
            await AuditService.log_event(
                actor_id=actor_id,
                actor_type="USER" if actor_id != "SYSTEM" else "SYSTEM",
                action="PRODUCT_UPDATED",
                entity_type="product",
                entity_id=str(product_id),
                source="ADMIN",
                metadata={"updated_fields": list(update_data.keys())}
            )
        return result

    @staticmethod
    async def add_or_update_recipe(product_id: str, recipe: ProductRecipe, actor_id: str = "SYSTEM") -> Optional[dict]:
        """
        Add a new recipe or update an existing recipe version in the product.
        """
        db = get_db()
        if not ObjectId.is_valid(product_id):
            return None

        product = await ProductService.get_product_by_id(product_id)
        if not product:
            raise ValueError(f"Product '{product_id}' not found")

        recipe_dict = recipe.model_dump()
        recipes = product.get("recipes", [])
        
        # Check if recipeId already exists in product
        existing_idx = next((i for i, r in enumerate(recipes) if r.get("recipeId") == recipe.recipeId), None)
        if existing_idx is not None:
            recipe_dict["updatedAt"] = datetime.utcnow()
            recipes[existing_idx] = recipe_dict
        else:
            recipe_dict["createdAt"] = datetime.utcnow()
            recipe_dict["updatedAt"] = datetime.utcnow()
            recipes.append(recipe_dict)

        result = await db.products.find_one_and_update(
            {"_id": ObjectId(product_id)},
            {"$set": {"recipes": recipes, "updatedAt": datetime.utcnow()}},
            return_document=True
        )

        await AuditService.log_event(
            actor_id=actor_id,
            actor_type="USER" if actor_id != "SYSTEM" else "SYSTEM",
            action="PRODUCT_RECIPE_SAVED",
            entity_type="product",
            entity_id=str(product_id),
            source="ADMIN",
            metadata={"recipeId": recipe.recipeId, "recipeName": recipe.recipeName, "version": recipe.version}
        )
        return result

    @staticmethod
    async def get_recipe(product_id: str, recipe_id: str) -> Optional[dict]:
        product = await ProductService.get_product_by_id(product_id)
        if not product:
            return None
        recipes = product.get("recipes", [])
        return next((r for r in recipes if r.get("recipeId") == recipe_id), None)

    @staticmethod
    async def delete_product(product_id: str, actor_id: str = "SYSTEM") -> bool:
        db = get_db()
        if not ObjectId.is_valid(product_id):
            return False
            
        result = await db.products.delete_one({"_id": ObjectId(product_id)})
        deleted = result.deleted_count > 0
        if deleted:
            await AuditService.log_event(
                actor_id=actor_id,
                actor_type="USER" if actor_id != "SYSTEM" else "SYSTEM",
                action="PRODUCT_DELETED",
                entity_type="product",
                entity_id=str(product_id),
                source="ADMIN"
            )
        return deleted
