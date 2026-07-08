from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class RecommendationRequest(BaseModel):
    device_id: Optional[int] = None
    building_id: Optional[int] = None


class RecommendationOut(BaseModel):
    id: int
    device_id: Optional[int]
    building_id: Optional[int]
    category: str
    title: str
    description: str
    estimated_savings_kwh: Optional[float] = None
    estimated_savings_pct: Optional[float] = None
    priority: str
    created_at: datetime

    class Config:
        from_attributes = True


class RecommendationResponse(BaseModel):
    device_id: Optional[int]
    building_id: Optional[int]
    recommendations: list[RecommendationOut]
