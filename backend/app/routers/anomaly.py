from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db import models
from app.schemas.anomaly import AnomalyDetectRequest, AnomalyDetectResponse
from app.services import anomaly_service, data_service
from app.ml.preprocessing import readings_to_frame

router = APIRouter(prefix="/anomaly", tags=["Anomaly Detection"])


def _devices_for_request(db: Session, req: AnomalyDetectRequest) -> list[models.Device]:
    if req.device_id:
        d = db.query(models.Device).filter(models.Device.id == req.device_id).first()
        if not d:
            raise HTTPException(status_code=404, detail="Device not found")
        return [d]
    if req.building_id:
        devices = db.query(models.Device).filter(models.Device.building_id == req.building_id).all()
        if not devices:
            raise HTTPException(status_code=404, detail="No devices found for this building")
        return devices
    raise HTTPException(status_code=400, detail="Provide either device_id or building_id")


@router.post("/detect", response_model=AnomalyDetectResponse)
def detect_anomalies(req: AnomalyDetectRequest, db: Session = Depends(get_db)):
    devices = _devices_for_request(db, req)
    all_anomalies = []
    total_scanned = 0

    for device in devices:
        readings = data_service.get_device_readings(db, device.id, req.lookback_days)
        df = readings_to_frame(readings)
        total_scanned += len(df)
        if df.empty:
            continue
        flagged = anomaly_service.detect(df, method=req.method, rated_capacity_kw=device.rated_capacity_kw)
        for _, row in flagged.iterrows():
            record = models.AnomalyRecord(
                device_id=device.id,
                timestamp=row["timestamp"],
                energy_kwh=row["energy_kwh"],
                method=row["method"],
                severity=row["severity"],
                score=row["score"],
                reason=row["reason"],
            )
            db.add(record)
            all_anomalies.append(record)

    db.commit()
    for r in all_anomalies:
        db.refresh(r)

    # surface high-severity anomalies as alerts
    for r in all_anomalies:
        if r.severity == "high":
            db.add(models.Alert(
                device_id=r.device_id,
                alert_type="anomaly",
                message=f"High-severity anomaly detected: {r.energy_kwh:.2f} kWh at {r.timestamp.strftime('%Y-%m-%d %H:%M')} ({r.reason})",
                severity="critical",
                window_start=r.timestamp,
                window_end=r.timestamp,
            ))
    db.commit()

    return AnomalyDetectResponse(
        device_id=req.device_id,
        building_id=req.building_id,
        total_points_scanned=total_scanned,
        anomalies_found=len(all_anomalies),
        anomalies=all_anomalies,
    )


@router.get("/history", response_model=list[dict])
def anomaly_history(device_id: int | None = None, building_id: int | None = None, limit: int = 100, db: Session = Depends(get_db)):
    q = db.query(models.AnomalyRecord)
    if device_id:
        q = q.filter(models.AnomalyRecord.device_id == device_id)
    elif building_id:
        device_ids = [d.id for d in db.query(models.Device).filter(models.Device.building_id == building_id).all()]
        q = q.filter(models.AnomalyRecord.device_id.in_(device_ids))
    records = q.order_by(models.AnomalyRecord.timestamp.desc()).limit(limit).all()
    return [{
        "id": r.id, "device_id": r.device_id, "timestamp": r.timestamp.isoformat(),
        "energy_kwh": r.energy_kwh, "method": r.method, "severity": r.severity,
        "score": r.score, "reason": r.reason,
    } for r in records]
