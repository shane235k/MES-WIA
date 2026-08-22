from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Query
from app.schemas.material_specification import (
    MaterialSpecificationCreate, MaterialSpecificationUpdate, MaterialSpecificationInDB
)
from app.schemas.inventory_lot import (
    InventoryLotCreate, InventoryLotReceive, InventoryLotAdjust, InventoryLotInDB
)
from app.schemas.material_reservation import MaterialReservationInDB
from app.schemas.material_transaction import MaterialTransactionInDB
from app.services.material_specification_service import MaterialSpecificationService
from app.services.inventory_lot_service import InventoryLotService
from app.services.material_reservation_service import MaterialReservationService
from app.services.material_transaction_service import MaterialTransactionService

router = APIRouter()

# ==========================================
# MATERIAL SPECIFICATIONS
# ==========================================

@router.post("/materials/specifications", response_model=MaterialSpecificationInDB, status_code=status.HTTP_201_CREATED)
async def create_specification(spec_in: MaterialSpecificationCreate):
    try:
        return await MaterialSpecificationService.create_specification(spec_in)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

@router.get("/materials/specifications", response_model=List[MaterialSpecificationInDB])
async def list_specifications(category: Optional[str] = None):
    return await MaterialSpecificationService.list_specifications(category=category)

@router.get("/materials/specifications/{id}", response_model=MaterialSpecificationInDB)
async def get_specification(id: str):
    spec = await MaterialSpecificationService.get_specification_by_id(id)
    if not spec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material specification not found")
    return spec

@router.put("/materials/specifications/{id}", response_model=MaterialSpecificationInDB)
async def update_specification(id: str, spec_update: MaterialSpecificationUpdate):
    try:
        spec = await MaterialSpecificationService.update_specification(id, spec_update)
        if not spec:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material specification not found")
        return spec
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.delete("/materials/specifications/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_specification(id: str):
    deleted = await MaterialSpecificationService.delete_specification(id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material specification not found")

# ==========================================
# INVENTORY LOTS
# ==========================================

@router.post("/inventory/lots", response_model=InventoryLotInDB, status_code=status.HTTP_201_CREATED)
async def create_lot(lot_in: InventoryLotCreate):
    try:
        return await InventoryLotService.create_lot(lot_in)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

@router.get("/inventory/lots", response_model=List[InventoryLotInDB])
async def list_lots(
    materialId: Optional[str] = None,
    specificationId: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status")
):
    return await InventoryLotService.list_lots(
        material_id=materialId,
        specification_id=specificationId,
        status=status_filter
    )

@router.get("/inventory/lots/{id}", response_model=InventoryLotInDB)
async def get_lot(id: str):
    lot = await InventoryLotService.get_lot_by_id(id)
    if not lot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventory lot not found")
    return lot

@router.post("/inventory/lots/{id}/receive", response_model=InventoryLotInDB)
async def receive_lot_stock(id: str, receive_in: InventoryLotReceive):
    try:
        return await InventoryLotService.receive_stock(id, receive_in)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/inventory/lots/{id}/adjust", response_model=InventoryLotInDB)
async def adjust_lot_stock(id: str, adjust_in: InventoryLotAdjust):
    try:
        return await InventoryLotService.adjust_stock(id, adjust_in)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

# ==========================================
# RESERVATIONS
# ==========================================

@router.get("/inventory/reservations", response_model=List[MaterialReservationInDB])
async def list_reservations(
    workOrderId: Optional[str] = None,
    operationId: Optional[str] = None,
    lotId: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status")
):
    return await MaterialReservationService.list_reservations(
        work_order_id=workOrderId,
        operation_id=operationId,
        lot_id=lotId,
        status=status_filter
    )

@router.post("/inventory/reservations/work-order/{work_order_id}/reserve")
async def reserve_for_work_order(work_order_id: str, actorId: str = Query("ADMIN")):
    try:
        return await MaterialReservationService.reserve_for_work_order(work_order_id, actor_id=actorId)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/inventory/reservations/work-order/{work_order_id}/release")
async def release_for_work_order(work_order_id: str, actorId: str = Query("ADMIN")):
    try:
        count = await MaterialReservationService.release_for_work_order(work_order_id, actor_id=actorId)
        return {"releasedCount": count, "message": f"Released {count} reservations"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

# ==========================================
# TRANSACTIONS LEDGER
# ==========================================

@router.get("/inventory/transactions", response_model=List[MaterialTransactionInDB])
async def list_transactions(
    materialId: Optional[str] = None,
    lotId: Optional[str] = None,
    workOrderId: Optional[str] = None,
    transactionType: Optional[str] = None,
    limit: int = 100
):
    return await MaterialTransactionService.list_transactions(
        material_id=materialId,
        lot_id=lotId,
        work_order_id=workOrderId,
        transaction_type=transactionType,
        limit=limit
    )

# ==========================================
# TRACEABILITY (GENEALOGY)
# ==========================================

@router.get("/inventory/trace/forward/{lot_number}")
async def get_forward_traceability(lot_number: str):
    try:
        return await MaterialReservationService.get_forward_traceability(lot_number)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.get("/inventory/trace/backward/{work_order_id}")
async def get_backward_traceability(work_order_id: str):
    try:
        return await MaterialReservationService.get_backward_traceability(work_order_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

# ==========================================
# WORK ORDER MATERIAL SUMMARY & COSTING
# ==========================================

@router.get("/work-orders/{work_order_id}/materials")
@router.get("/inventory/work-orders/{work_order_id}/materials")
async def get_work_order_material_summary(work_order_id: str):
    try:
        return await MaterialReservationService.get_work_order_material_summary(work_order_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

# ==========================================
# LEGACY MATERIAL MIGRATION
# ==========================================

@router.post("/inventory/migrate-legacy")
async def migrate_legacy_materials():
    return await InventoryLotService.migrate_legacy_materials()
