from typing import List, TYPE_CHECKING

from sqlalchemy import Boolean, Integer, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.dye_house import DyeHouse
    from app.models.fastness_check import FastnessCheck


class SampleSlot(Base):
    """染坊留样格位：入格的色牢度样条占用格位。"""

    __tablename__ = "sample_slots"
    __table_args__ = (
        UniqueConstraint("dye_house_id", "slot_code", name="uq_house_slot_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    dye_house_id: Mapped[int] = mapped_column(ForeignKey("dye_houses.id"), nullable=False, index=True)
    slot_code: Mapped[str] = mapped_column(String(64), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    stored_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    dye_house: Mapped["DyeHouse"] = relationship("DyeHouse", back_populates="sample_slots")
    checks: Mapped[List["FastnessCheck"]] = relationship(
        "FastnessCheck", back_populates="sample_slot"
    )
