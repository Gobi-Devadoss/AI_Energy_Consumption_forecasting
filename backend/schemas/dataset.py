from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class BuildingOut(BaseModel):
    id: int
    name: str
    location: Optional[str] = None

    class Config:
        from_attributes = True


class DeviceOut(BaseModel):
    id: int
    building_id: int
    external_id: str
    name: Optional[str] = None
    device_type: Optional[str] = None
    rated_capacity_kw: Optional[float] = None

    class Config:
        from_attributes = True


class UploadSummary(BaseModel):
    batch_id: str
    rows_ingested: int
    rows_rejected: int
    buildings_created: int
    devices_created: int
    date_range_start: Optional[datetime]
    date_range_end: Optional[datetime]
    warnings: list[str] = Field(default_factory=list)


class ReadingOut(BaseModel):
    timestamp: datetime
    device_id: int
    energy_kwh: float
    temperature_c: Optional[float] = None
    occupancy: Optional[float] = None
    is_interpolated: bool = False

    class Config:
        from_attributes = True
