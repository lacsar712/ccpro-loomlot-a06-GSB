from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class SampleSlotCreate(BaseModel):
    dye_house_id: int = Field(..., alias="dyeHouseId")
    slot_code: str = Field(..., min_length=1, max_length=64, alias="slotCode")
    capacity: int = Field(..., ge=1, alias="capacity")
    is_active: bool = Field(True, alias="isActive")

    model_config = ConfigDict(populate_by_name=True)


class SampleSlotUpdate(BaseModel):
    dye_house_id: Optional[int] = Field(None, alias="dyeHouseId")
    slot_code: Optional[str] = Field(None, min_length=1, max_length=64, alias="slotCode")
    capacity: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = Field(None, alias="isActive")

    model_config = ConfigDict(populate_by_name=True)


class SampleSlotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    dye_house_id: int = Field(serialization_alias="dyeHouseId")
    slot_code: str = Field(serialization_alias="slotCode")
    capacity: int
    stored_count: int = Field(serialization_alias="storedCount")
    is_active: bool = Field(serialization_alias="isActive")


class SampleBindingCreate(BaseModel):
    fastness_check_id: int = Field(..., alias="fastnessCheckId")

    model_config = ConfigDict(populate_by_name=True)


class SampleBindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    slot_id: int = Field(serialization_alias="slotId")
    fastness_check_id: int = Field(serialization_alias="fastnessCheckId")
    bound_at: datetime = Field(serialization_alias="boundAt")
