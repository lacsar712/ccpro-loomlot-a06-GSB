from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.dye_house import DyeHouse
from app.models.dye_lot import DyeLot
from app.models.fastness_check import FastnessCheck
from app.models.sample_binding import SampleBinding
from app.models.sample_slot import SampleSlot
from app.models.user import User
from app.models.vat import Vat
from app.schemas.sample_slot import (
    SampleBindingCreate,
    SampleBindingOut,
    SampleSlotCreate,
    SampleSlotUpdate,
    SampleSlotOut,
)

router = APIRouter(prefix="/api/sample-slots", tags=["sample-slots"])


@router.get("", response_model=List[SampleSlotOut])
def list_slots(
    dye_house_id: Optional[int] = Query(None, alias="dyeHouseId"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(SampleSlot)
    if dye_house_id is not None:
        q = q.filter(SampleSlot.dye_house_id == dye_house_id)
    return q.order_by(SampleSlot.dye_house_id, SampleSlot.id).all()


@router.post("", response_model=SampleSlotOut, status_code=status.HTTP_201_CREATED)
def create_slot(
    payload: SampleSlotCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    house = db.query(DyeHouse).filter(DyeHouse.id == payload.dye_house_id).first()
    if not house:
        raise HTTPException(status_code=400, detail="染坊不存在")
    item = SampleSlot(
        dye_house_id=payload.dye_house_id,
        slot_code=payload.slot_code,
        capacity=payload.capacity,
        stored_count=0,
        is_active=payload.is_active,
    )
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="同坊格位码已存在")
    db.refresh(item)
    return item


@router.get("/bindings", response_model=List[SampleBindingOut])
def list_bindings(
    slot_id: Optional[int] = Query(None, alias="slotId"),
    fastness_check_id: Optional[int] = Query(None, alias="fastnessCheckId"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(SampleBinding)
    if slot_id is not None:
        q = q.filter(SampleBinding.slot_id == slot_id)
    if fastness_check_id is not None:
        q = q.filter(SampleBinding.fastness_check_id == fastness_check_id)
    return q.order_by(SampleBinding.id.desc()).all()


@router.get("/{slot_id}", response_model=SampleSlotOut)
def get_slot(
    slot_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    item = db.query(SampleSlot).filter(SampleSlot.id == slot_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="留样格位不存在")
    return item


@router.put("/{slot_id}", response_model=SampleSlotOut)
def update_slot(
    slot_id: int,
    payload: SampleSlotUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    item = db.query(SampleSlot).filter(SampleSlot.id == slot_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="留样格位不存在")
    data = payload.model_dump(exclude_unset=True)

    # 停用格位：仅主管，且已存必须为 0
    if data.get("is_active") is False and item.is_active:
        if current.role != "admin":
            raise HTTPException(status_code=403, detail="停用格位仅染坊主管可执行")
        if item.stored_count > 0:
            raise HTTPException(status_code=409, detail=f"格位已存 {item.stored_count} 条留样，须清空后才能停用")

    if "dye_house_id" in data and data["dye_house_id"] != item.dye_house_id:
        house = db.query(DyeHouse).filter(DyeHouse.id == data["dye_house_id"]).first()
        if not house:
            raise HTTPException(status_code=400, detail="染坊不存在")
        if item.stored_count > 0:
            raise HTTPException(status_code=409, detail="格位仍有留样，不能改属染坊")

    if "capacity" in data and data["capacity"] < item.stored_count:
        raise HTTPException(
            status_code=409,
            detail=f"可存条数不可小于已存条数（{item.stored_count}）",
        )

    for k, v in data.items():
        setattr(item, k, v)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="同坊格位码已存在")
    db.refresh(item)
    return item


@router.post("/{slot_id}/bindings", response_model=SampleBindingOut, status_code=status.HTTP_201_CREATED)
def bind_check(
    slot_id: int,
    payload: SampleBindingCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """入格：绑定一条色牢度，已存加一。操作员可执行。"""
    slot = db.query(SampleSlot).filter(SampleSlot.id == slot_id).first()
    if not slot:
        raise HTTPException(status_code=404, detail="留样格位不存在")
    if not slot.is_active:
        raise HTTPException(status_code=409, detail="格位已停用，不能入格")
    if slot.stored_count >= slot.capacity:
        raise HTTPException(
            status_code=409,
            detail=f"格位已满（{slot.stored_count}/{slot.capacity}），无法入格",
        )
    check = (
        db.query(FastnessCheck)
        .filter(FastnessCheck.id == payload.fastness_check_id)
        .first()
    )
    if not check:
        raise HTTPException(status_code=400, detail="色牢度抽检不存在")

    # 入格互证：色牢度必须属于该格位所属染坊（色牢度→染程→染缸→染坊）
    lot_house_id = (
        db.query(Vat.dye_house_id)
        .join(DyeLot, DyeLot.vat_id == Vat.id)
        .filter(DyeLot.id == check.dye_lot_id)
        .scalar()
    )
    if lot_house_id != slot.dye_house_id:
        raise HTTPException(status_code=409, detail="色牢度所属染程不在该格位的染坊，不能入格")

    binding = SampleBinding(
        slot_id=slot.id,
        fastness_check_id=check.id,
        bound_at=datetime.now(timezone.utc),
    )
    slot.stored_count += 1
    db.add(binding)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="该色牢度已入格，一条只能入一次")
    db.refresh(binding)
    return binding


@router.delete("/bindings/{binding_id}", status_code=status.HTTP_204_NO_CONTENT)
def unbind_check(
    binding_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """取出留样：解除绑定并将已存减一。"""
    binding = db.query(SampleBinding).filter(SampleBinding.id == binding_id).first()
    if not binding:
        raise HTTPException(status_code=404, detail="入格记录不存在")
    slot = db.query(SampleSlot).filter(SampleSlot.id == binding.slot_id).first()
    if slot and slot.stored_count > 0:
        slot.stored_count -= 1
    db.delete(binding)
    db.commit()


@router.delete("/{slot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_slot(
    slot_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    item = db.query(SampleSlot).filter(SampleSlot.id == slot_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="留样格位不存在")
    if item.stored_count > 0:
        raise HTTPException(status_code=409, detail="格位仍有留样，无法删除")
    db.delete(item)
    db.commit()
