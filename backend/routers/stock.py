"""Stock router — role-filtered CRUD for stock items."""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.middleware.auth import get_current_user
from backend.services import stock_service
from backend import models, schemas

router = APIRouter(prefix="/stock", tags=["stock"])


@router.get("", response_model=list[schemas.StockOut])
def list_stock(
    warehouse_id: Optional[int] = Query(None),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return stock_service.get_stock(db, current_user, warehouse_id)


@router.get("/serial", response_model=list[schemas.StockSerialOut])
def list_serial_stock(
    warehouse_id: Optional[int] = Query(None),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return stock_service.get_serial_stock(db, current_user, warehouse_id)


@router.get("/{item_id}", response_model=schemas.StockOut)
def get_stock_item(
    item_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return stock_service._get_stock_item_or_403(db, current_user, item_id)


@router.get("/serial/{item_id}", response_model=schemas.StockSerialOut)
def get_serial_item(
    item_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return stock_service._get_serial_item_or_403(db, current_user, item_id)


@router.put("/{item_id}", response_model=schemas.StockOut)
def update_stock_item(
    item_id: int,
    body: schemas.StockUpdateRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return stock_service.update_stock_item(
        db, current_user, item_id, body.model_dump(exclude_none=True)
    )


@router.put("/serial/{item_id}", response_model=schemas.StockSerialOut)
def update_serial_item(
    item_id: int,
    body: schemas.StockSerialUpdateRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return stock_service.update_serial_item(
        db, current_user, item_id, body.model_dump(exclude_none=True)
    )
