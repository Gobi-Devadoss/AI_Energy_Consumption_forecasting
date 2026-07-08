from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Literal

Horizon = Literal["24h", "7d", "30d"]
Granularity = Literal["hourly", "daily"]
ModelChoice = Literal["auto", "prophet", "lstm", "arima", "regression"]


class ForecastRequest(BaseModel):
    device_id: Optional[int] = None
    building_id: Optional[int] = None
    horizon: Horizon = "24h"
    granularity: Granularity = "hourly"
    model: ModelChoice = "auto"


class ForecastPointOut(BaseModel):
    timestamp: datetime
    predicted_kwh: float
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None
    is_peak: bool = False

    class Config:
        from_attributes = True


class ForecastResponse(BaseModel):
    run_id: int
    device_id: Optional[int]
    building_id: Optional[int]
    granularity: str
    horizon: str
    model_used: str
    mae: Optional[float] = None
    rmse: Optional[float] = None
    mape: Optional[float] = None
    points: list[ForecastPointOut]
    peak_windows: list[dict] = []


class ModelComparisonResponse(BaseModel):
    device_id: Optional[int]
    building_id: Optional[int]
    horizon: str
    results: list[dict]
