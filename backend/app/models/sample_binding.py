from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.sample_slot import SampleSlot
    from app.models.fastness_check import FastnessCheck


class SampleBinding(Base):
    """入格记录：一条色牢度抽检对应一次留样入格（一条只能入一次）。"""

    __tablename__ = "sample_bindings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    slot_id: Mapped[int] = mapped_column(
        ForeignKey("sample_slots.id"), nullable=False, index=True
    )
    fastness_check_id: Mapped[int] = mapped_column(
        ForeignKey("fastness_checks.id"), unique=True, nullable=False, index=True
    )
    bound_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    slot: Mapped["SampleSlot"] = relationship(back_populates="bindings")
    fastness_check: Mapped["FastnessCheck"] = relationship(back_populates="sample_binding")
