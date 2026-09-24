from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.dye_lot import DyeLot
from app.models.user import User
from app.models.vat import Vat
from app.rules import NORMAL_FABRIC_KG, fabric_kg_limit, release_checks_slots
from app.schemas.dye_lot import DyeLotCreate, DyeLotUpdate, DyeLotOut

router = APIRouter(prefix="/api/dye-lots", tags=["dye-lots"])

ALLOWED_VAT_STATUSES = {"ready", "dyeing"}


def ensure_fabric_limit(db: Session, vat: Vat, fabric_kg: float) -> None:
    """按染缸所属染坊的留样占位情况校验布重上限。"""
    limit = fabric_kg_limit(db, vat.dye_house_id)
    if fabric_kg > limit:
        if limit < NORMAL_FABRIC_KG:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"布重 {fabric_kg}kg 超过该坊当前上限 {limit:g}kg："
                    "该坊启用格位已有留样占位，新建染程布重上限降为 50 千克"
                ),
            )
        raise HTTPException(
            status_code=400,
            detail=f"布重 {fabric_kg}kg 超过新建染程布重上限 {limit:g} 千克",
        )


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
    ensure_fabric_limit(db, vat, payload.fabric_kg)
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
    target_vat = item.vat
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
    if "fabric_kg" in data or ("vat_id" in data and data["vat_id"] != item.vat_id):
        ensure_fabric_limit(db, target_vat, data.get("fabric_kg", item.fabric_kg))
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
    # 先释放其色牢度在留样格的占用，再随级联删除，保证已存计数一致
    release_checks_slots(db, [ck.id for ck in item.fastness_checks])
    db.delete(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="该染程仍有关联记录，无法删除")
