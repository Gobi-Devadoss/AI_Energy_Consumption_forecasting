from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Literal

AnomalyMethod = Literal["auto", "isolation_forest", "zscore", "threshold"]


class AnomalyDetectRequest(BaseModel):
    device_id: Optional[int] = None
    building_id: Optional[int] = None
    method: AnomalyMethod = "auto"
    lookback_days: int = 30


class AnomalyOut(BaseModel):
    id: int
    device_id: int
    timestamp: datetime
    energy_kwh: float
    method: str
    severity: str
    score: Optional[float] = None
    reason: Optional[str] = None

    class Config:
        from_attributes = True


class AnomalyDetectResponse(BaseModel):
    device_id: Optional[int]
    building_id: Optional[int]
    total_points_scanned: int
    anomalies_found: int
    anomalies: list[AnomalyOut]
