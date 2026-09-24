from typing import List, TYPE_CHECKING

from sqlalchemy import String, Integer, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.dye_house import DyeHouse
    from app.models.sample_binding import SampleBinding


class SampleSlot(Base):
    """留样格位：存放色牢度留样样品条。"""

    __tablename__ = "sample_slots"
    __table_args__ = (
        UniqueConstraint("dye_house_id", "slot_code", name="uq_house_slot_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    dye_house_id: Mapped[int] = mapped_column(
        ForeignKey("dye_houses.id"), nullable=False, index=True
    )
    slot_code: Mapped[str] = mapped_column(String(64), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    stored_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    dye_house: Mapped["DyeHouse"] = relationship(back_populates="sample_slots")
    bindings: Mapped[List["SampleBinding"]] = relationship(
        "SampleBinding", back_populates="slot", cascade="all, delete-orphan"
    )
