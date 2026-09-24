"""留样格位与布重上限联动规则。"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.sample_binding import SampleBinding
from app.models.sample_slot import SampleSlot

# 常规新建染程布重上限（千克）
NORMAL_FABRIC_KG = 100.0
# 该坊启用格位有留样占位时的降限（千克）
OCCUPIED_FABRIC_KG = 50.0


def active_stored_total(db: Session, dye_house_id: int) -> int:
    """该坊所有【启用】格位的已存条数合计。"""
    total = (
        db.query(func.coalesce(func.sum(SampleSlot.stored_count), 0))
        .filter(SampleSlot.dye_house_id == dye_house_id)
        .filter(SampleSlot.is_active.is_(True))
        .scalar()
    )
    return int(total or 0)


def fabric_kg_limit(db: Session, dye_house_id: int) -> float:
    """该坊当前新建染程布重上限：启用格位已存合计 > 0 时降为 50kg，否则 100kg。"""
    if active_stored_total(db, dye_house_id) > 0:
        return OCCUPIED_FABRIC_KG
    return NORMAL_FABRIC_KG


def release_checks_slots(db: Session, check_ids) -> None:
    """这些色牢度即将被（级联）删除前，把其入格占用的格位已存减一。

    入格记录本身由外键/ORM 级联删除，这里只维护 stored_count 计数一致。
    """
    check_ids = list(check_ids)
    if not check_ids:
        return
    bindings = (
        db.query(SampleBinding)
        .filter(SampleBinding.fastness_check_id.in_(check_ids))
        .all()
    )
    for b in bindings:
        slot = db.query(SampleSlot).filter(SampleSlot.id == b.slot_id).first()
        if slot and slot.stored_count > 0:
            slot.stored_count -= 1
