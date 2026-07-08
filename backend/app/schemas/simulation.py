from pydantic import BaseModel
from typing import Optional, Literal

ScenarioType = Literal["occupancy_change", "temperature_change", "device_shutdown", "peak_hour_reduction"]


class SimulationRequest(BaseModel):
    device_id: Optional[int] = None
    building_id: Optional[int] = None
    scenario_type: ScenarioType
    # Generic parameter bag - interpreted per scenario_type by the simulation service
    occupancy_change_pct: Optional[float] = None       # e.g. +20 means occupancy up 20%
    temperature_change_c: Optional[float] = None        # e.g. +3 means 3C hotter
    shutdown_hours: Optional[list[int]] = None           # hours of day (0-23) device is switched off
    peak_reduction_pct: Optional[float] = None           # e.g. 15 means cut peak-hour load by 15%
    electricity_rate_per_kwh: Optional[float] = None
    lookback_days: int = 30


class SimulationResponse(BaseModel):
    scenario_type: str
    device_id: Optional[int]
    building_id: Optional[int]
    baseline_kwh: float
    projected_kwh: float
    savings_kwh: float
    savings_pct: float
    cost_impact: float
    currency_rate_used: float
    explanation: str
