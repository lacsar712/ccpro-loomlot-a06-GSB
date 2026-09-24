from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.dye_lot import DyeLot
from app.models.fastness_check import FastnessCheck
from app.models.sample_slot import SampleSlot
from app.models.user import User
from app.models.vat import Vat
from app.routers.sample_slots import OCCUPIED_FABRIC_KG_CAP, house_occupied_by_samples
from app.schemas.dye_lot import DyeLotCreate, DyeLotUpdate, DyeLotOut

router = APIRouter(prefix="/api/dye-lots", tags=["dye-lots"])

ALLOWED_VAT_STATUSES = {"ready", "dyeing"}


@router.get("", response_model=List[DyeLotOut])
def list_dye_lots(
    vat_id: Optional[int] = Query(None, alias="vatId"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(DyeLot)
    if vat_id is not None:
        q = q.filter(DyeLot.vat_id == vat_id)
    return q.order_by(DyeLot.id.desc()).all()


@router.post("", response_model=DyeLotOut, status_code=status.HTTP_201_CREATED)
def create_dye_lot(
    payload: DyeLotCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    vat = db.query(Vat).filter(Vat.id == payload.vat_id).first()
    if not vat:
        raise HTTPException(status_code=400, detail="染缸不存在")
    if vat.status not in ALLOWED_VAT_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"染缸状态为「{vat.status}」，仅 ready 或 dyeing 时可新建染程",
        )
    if (
        payload.fabric_kg > OCCUPIED_FABRIC_KG_CAP
        and house_occupied_by_samples(db, vat.dye_house_id)
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                f"因留样占位，该坊新建染程布重上限为 {OCCUPIED_FABRIC_KG_CAP:g} 千克，"
                f"当前 {payload.fabric_kg:g} 千克超限，请先清空留样格位"
            ),
        )
    item = DyeLot(
        vat_id=payload.vat_id,
        recipe_name=payload.recipe_name,
        fabric_kg=payload.fabric_kg,
        started_at=payload.started_at,
        operator_name=payload.operator_name,
    )
    vat.status = "dyeing"
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/{lot_id}", response_model=DyeLotOut)
def get_dye_lot(
    lot_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    item = db.query(DyeLot).filter(DyeLot.id == lot_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="染程不存在")
    return item


@router.put("/{lot_id}", response_model=DyeLotOut)
def update_dye_lot(
    lot_id: int,
    payload: DyeLotUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    item = db.query(DyeLot).filter(DyeLot.id == lot_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="染程不存在")
    data = payload.model_dump(exclude_unset=True)
    target_vat = None
    if "vat_id" in data and data["vat_id"] != item.vat_id:
        target_vat = db.query(Vat).filter(Vat.id == data["vat_id"]).first()
        if not target_vat:
            raise HTTPException(status_code=400, detail="染缸不存在")
        if target_vat.status not in ALLOWED_VAT_STATUSES:
            raise HTTPException(
                status_code=409,
                detail=f"目标染缸状态为「{target_vat.status}」，无法改挂染程",
            )
        target_vat.status = "dyeing"

    # 留样占位降限同样约束改挂/改重
    if "fabric_kg" in data or target_vat is not None:
        house_id = (
            target_vat.dye_house_id if target_vat is not None else item.vat.dye_house_id
        )
        fabric_kg = data.get("fabric_kg", item.fabric_kg)
        if fabric_kg > OCCUPIED_FABRIC_KG_CAP and house_occupied_by_samples(db, house_id):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"因留样占位，该坊染程布重上限为 {OCCUPIED_FABRIC_KG_CAP:g} 千克，"
                    f"当前 {fabric_kg:g} 千克超限，请先清空留样格位"
                ),
            )

    for k, v in data.items():
        setattr(item, k, v)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{lot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dye_lot(
    lot_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    item = db.query(DyeLot).filter(DyeLot.id == lot_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="染程不存在")
    # 染程下已入格的色牢度会随级联删除，先回退相应格位已存计数
    bound = (
        db.query(FastnessCheck)
        .filter(
            FastnessCheck.dye_lot_id == lot_id,
            FastnessCheck.sample_slot_id.isnot(None),
        )
        .all()
    )
    for check in bound:
        slot = db.query(SampleSlot).filter(SampleSlot.id == check.sample_slot_id).first()
        if slot and slot.stored_count > 0:
            slot.stored_count -= 1
    db.delete(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="该染程仍有关联记录，无法删除")
