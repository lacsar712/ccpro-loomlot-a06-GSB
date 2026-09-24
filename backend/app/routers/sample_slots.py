from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.dye_house import DyeHouse
from app.models.fastness_check import FastnessCheck
from app.models.sample_slot import SampleSlot
from app.models.user import User
from app.schemas.sample_slot import (
    SampleSlotCreate,
    SampleSlotUpdate,
    SampleStoreIn,
    SampleSlotOut,
)

router = APIRouter(prefix="/api/sample-slots", tags=["sample-slots"])

# 留样占位期间，该坊新建染程的布重上限（千克）
OCCUPIED_FABRIC_KG_CAP = 50.0


def occupied_enabled_slot_stored(db: Session, dye_house_id: int) -> int:
    """某染坊所有「启用」格位的已存条数合计。"""
    total = (
        db.query(func.coalesce(func.sum(SampleSlot.stored_count), 0))
        .filter(
            SampleSlot.dye_house_id == dye_house_id,
            SampleSlot.enabled.is_(True),
        )
        .scalar()
    )
    return int(total or 0)


def house_occupied_by_samples(db: Session, dye_house_id: int) -> bool:
    """启用格位已存合计大于 0 时，该坊处于留样占位状态。"""
    return occupied_enabled_slot_stored(db, dye_house_id) > 0


@router.get("", response_model=List[SampleSlotOut])
def list_slots(
    dye_house_id: Optional[int] = Query(None, alias="dyeHouseId"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(SampleSlot)
    if dye_house_id is not None:
        q = q.filter(SampleSlot.dye_house_id == dye_house_id)
    return q.order_by(SampleSlot.id).all()


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
        enabled=payload.enabled,
    )
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="同坊格位码已存在")
    db.refresh(item)
    return item


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
    current_user: User = Depends(get_current_user),
):
    item = db.query(SampleSlot).filter(SampleSlot.id == slot_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="留样格位不存在")

    data = payload.model_dump(exclude_unset=True)

    # 停用格位：仅主管可操作，且格位必须已清空
    if data.get("enabled") is False and item.enabled:
        if current_user.role != "admin":
            raise HTTPException(status_code=403, detail="停用留样格位需染坊主管权限")
        if item.stored_count > 0:
            raise HTTPException(
                status_code=409,
                detail=f"格位内仍有留样 {item.stored_count} 条，须先全部取出方可停用",
            )

    # 容量不得小于现存条数，否则格位会处于越界状态
    new_capacity = data.get("capacity")
    if new_capacity is not None and new_capacity < item.stored_count:
        raise HTTPException(
            status_code=400,
            detail=f"可存条数不得小于已存条数（当前已存 {item.stored_count}）",
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


@router.post("/{slot_id}/store", response_model=SampleSlotOut)
def store_check(
    slot_id: int,
    payload: SampleStoreIn,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """入格：绑定一条色牢度，已存加一。操作员可入格。"""
    slot = db.query(SampleSlot).filter(SampleSlot.id == slot_id).first()
    if not slot:
        raise HTTPException(status_code=404, detail="留样格位不存在")
    if not slot.enabled:
        raise HTTPException(status_code=409, detail="格位已停用，无法入格")

    check = db.query(FastnessCheck).filter(FastnessCheck.id == payload.fastness_check_id).first()
    if not check:
        raise HTTPException(status_code=400, detail="色牢度抽检记录不存在")
    if check.sample_slot_id is not None:
        raise HTTPException(status_code=409, detail="该色牢度已入格，一条色牢度只能入一次")
    if slot.stored_count >= slot.capacity:
        raise HTTPException(
            status_code=409,
            detail=f"格位已满（可存 {slot.capacity} 条），无法继续入格",
        )

    check.sample_slot_id = slot.id
    slot.stored_count += 1
    db.commit()
    db.refresh(slot)
    return slot


@router.post("/{slot_id}/unstore", response_model=SampleSlotOut)
def unstore_check(
    slot_id: int,
    payload: SampleStoreIn,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """出格：解除绑定，已存减一。已存全部清零后该坊恢复原布重规则。"""
    slot = db.query(SampleSlot).filter(SampleSlot.id == slot_id).first()
    if not slot:
        raise HTTPException(status_code=404, detail="留样格位不存在")

    check = db.query(FastnessCheck).filter(FastnessCheck.id == payload.fastness_check_id).first()
    if not check:
        raise HTTPException(status_code=400, detail="色牢度抽检记录不存在")
    if check.sample_slot_id != slot.id:
        raise HTTPException(status_code=409, detail="该色牢度不在此格位内")
    if slot.stored_count <= 0:
        raise HTTPException(status_code=409, detail="格位已存为 0，无可取出的留样")

    check.sample_slot_id = None
    slot.stored_count -= 1
    db.commit()
    db.refresh(slot)
    return slot


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
        raise HTTPException(status_code=409, detail="格位内仍有留样，无法删除")
    db.delete(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="该格位仍有关联记录，无法删除")
