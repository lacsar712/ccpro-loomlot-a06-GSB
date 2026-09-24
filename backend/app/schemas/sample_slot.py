from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class SampleSlotCreate(BaseModel):
    dye_house_id: int = Field(..., alias="dyeHouseId")
    slot_code: str = Field(..., min_length=1, max_length=64, alias="slotCode")
    capacity: int = Field(..., ge=1, alias="capacity")
    enabled: bool = True

    model_config = ConfigDict(populate_by_name=True)


class SampleSlotUpdate(BaseModel):
    slot_code: Optional[str] = Field(None, min_length=1, max_length=64, alias="slotCode")
    capacity: Optional[int] = Field(None, ge=1, alias="capacity")
    enabled: Optional[bool] = None

    model_config = ConfigDict(populate_by_name=True)


class SampleStoreIn(BaseModel):
    fastness_check_id: int = Field(..., alias="fastnessCheckId")

    model_config = ConfigDict(populate_by_name=True)


class SampleSlotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    dye_house_id: int = Field(serialization_alias="dyeHouseId")
    slot_code: str = Field(serialization_alias="slotCode")
    capacity: int
    stored_count: int = Field(serialization_alias="storedCount")
    enabled: bool
