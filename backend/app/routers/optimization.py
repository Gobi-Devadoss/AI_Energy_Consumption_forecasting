from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db import models
from app.schemas.optimization import RecommendationRequest, RecommendationResponse
from app.services import optimization_service, forecasting_service, data_service
from app.ml.preprocessing import readings_to_frame, regularize_hourly

router = APIRouter(prefix="/optimization", tags=["Optimization"])


@router.post("/recommendations", response_model=RecommendationResponse)
def get_recommendations(req: RecommendationRequest, db: Session = Depends(get_db)):
    if not req.device_id and not req.building_id:
        raise HTTPException(status_code=400, detail="Provide either device_id or building_id")

    devices = []
    if req.device_id:
        d = db.query(models.Device).filter(models.Device.id == req.device_id).first()
        if not d:
            raise HTTPException(status_code=404, detail="Device not found")
        devices = [d]
    else:
        devices = db.query(models.Device).filter(models.Device.building_id == req.building_id).all()
        if not devices:
            raise HTTPException(status_code=404, detail="No devices found for this building")

    all_recs = []
    for device in devices:
        readings = data_service.get_device_readings(db, device.id, lookback_days=30)
        raw = readings_to_frame(readings)
        hourly = regularize_hourly(raw)
        if hourly.empty or len(hourly) < 24:
            continue

        # Try to reuse the latest forecast's peak windows if available, else compute quickly from history
        latest_run = db.query(models.ForecastRun).filter(
            models.ForecastRun.device_id == device.id, models.ForecastRun.status == "completed"
        ).order_by(models.ForecastRun.created_at.desc()).first()
        peak_windows = []
        if latest_run:
            points = [{
                "timestamp": p.timestamp, "predicted_kwh": p.predicted_kwh, "is_peak": p.is_peak
            } for p in latest_run.points]
            import pandas as pd
            pdf = pd.DataFrame(points)
            if not pdf.empty:
                peak_windows = forecasting_service.peak_windows(pdf)

        recs = optimization_service.generate_recommendations(
            hourly, device.name or device.external_id, device.device_type, peak_windows
        )
        for rec in recs:
            record = models.Recommendation(
                device_id=device.id,
                building_id=device.building_id,
                category=rec["category"],
                title=rec["title"],
                description=rec["description"],
                estimated_savings_kwh=rec["estimated_savings_kwh"],
                estimated_savings_pct=rec["estimated_savings_pct"],
                priority=rec["priority"],
            )
            db.add(record)
            all_recs.append(record)

    db.commit()
    for r in all_recs:
        db.refresh(r)

    return RecommendationResponse(device_id=req.device_id, building_id=req.building_id, recommendations=all_recs)


@router.get("/recommendations/history", response_model=list[dict])
def recommendation_history(device_id: int | None = None, building_id: int | None = None, limit: int = 50, db: Session = Depends(get_db)):
    q = db.query(models.Recommendation)
    if device_id:
        q = q.filter(models.Recommendation.device_id == device_id)
    elif building_id:
        q = q.filter(models.Recommendation.building_id == building_id)
    records = q.order_by(models.Recommendation.created_at.desc()).limit(limit).all()
    return [{
        "id": r.id, "category": r.category, "title": r.title, "description": r.description,
        "estimated_savings_kwh": r.estimated_savings_kwh, "estimated_savings_pct": r.estimated_savings_pct,
        "priority": r.priority, "created_at": r.created_at.isoformat(),
    } for r in records]
