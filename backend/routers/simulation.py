from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import json
from core.database import get_db
from model import models
from schemas.simulation import SimulationRequest, SimulationResponse
from services import simulation_service, data_service
from ml.preprocessing import readings_to_frame, regularize_hourly

router = APIRouter(prefix="/simulation", tags=["Scenario Simulation"])


@router.post("/run", response_model=SimulationResponse)
def run_simulation(req: SimulationRequest, db: Session = Depends(get_db)):
    if not req.device_id and not req.building_id:
        raise HTTPException(status_code=400, detail="Provide either device_id or building_id")

    if req.device_id:
        readings = data_service.get_device_readings(db, req.device_id, req.lookback_days)
    else:
        readings = data_service.get_building_readings(db, req.building_id, req.lookback_days)

    raw = readings_to_frame(readings)
    hourly = regularize_hourly(raw) if req.device_id else raw
    if req.building_id and not raw.empty:
        hourly = raw.groupby("timestamp", as_index=False).agg({"energy_kwh": "sum"})

    if hourly.empty:
        raise HTTPException(status_code=400, detail="No historical data available to simulate against")

    try:
        result = simulation_service.run_simulation(hourly, req.scenario_type, req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    run = models.SimulationRun(
        device_id=req.device_id,
        building_id=req.building_id,
        scenario_type=req.scenario_type,
        parameters_json=json.dumps(req.model_dump(exclude={"device_id", "building_id", "scenario_type"})),
        baseline_kwh=result["baseline_kwh"],
        projected_kwh=result["projected_kwh"],
        savings_kwh=result["savings_kwh"],
        savings_pct=result["savings_pct"],
        cost_impact=result["cost_impact"],
    )
    db.add(run)
    db.commit()

    return SimulationResponse(
        scenario_type=req.scenario_type,
        device_id=req.device_id,
        building_id=req.building_id,
        **result,
    )


@router.get("/history", response_model=list[dict])
def simulation_history(device_id: int | None = None, building_id: int | None = None, limit: int = 30, db: Session = Depends(get_db)):
    q = db.query(models.SimulationRun)
    if device_id:
        q = q.filter(models.SimulationRun.device_id == device_id)
    elif building_id:
        q = q.filter(models.SimulationRun.building_id == building_id)
    runs = q.order_by(models.SimulationRun.created_at.desc()).limit(limit).all()
    return [{
        "id": r.id, "scenario_type": r.scenario_type, "baseline_kwh": r.baseline_kwh,
        "projected_kwh": r.projected_kwh, "savings_kwh": r.savings_kwh, "savings_pct": r.savings_pct,
        "cost_impact": r.cost_impact, "created_at": r.created_at.isoformat(),
    } for r in runs]
