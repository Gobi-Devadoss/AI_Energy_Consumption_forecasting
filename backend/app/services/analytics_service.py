"""
Read-side aggregation queries powering the analytics dashboard: historical
usage summaries, device-wise breakdowns, and forecast-accuracy rollups.
Kept separate from forecasting/anomaly/optimization services since this
layer only reads already-persisted data and never trains models.
"""
from __future__ import annotations
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from app.db import models


def historical_summary(db: Session, device_id: int | None, building_id: int | None, days: int = 30) -> dict:
    cutoff = datetime.utcnow() - timedelta(days=days)
    q = db.query(models.EnergyReading).join(models.Device)
    if device_id:
        q = q.filter(models.EnergyReading.device_id == device_id)
    elif building_id:
        q = q.filter(models.Device.building_id == building_id)
    q = q.filter(models.EnergyReading.timestamp >= cutoff)
    readings = q.order_by(models.EnergyReading.timestamp).all()

    if not readings:
        return {"total_kwh": 0, "avg_kwh": 0, "peak_kwh": 0, "peak_timestamp": None, "points": []}

    total = sum(r.energy_kwh for r in readings)
    peak = max(readings, key=lambda r: r.energy_kwh)
    return {
        "total_kwh": round(total, 2),
        "avg_kwh": round(total / len(readings), 3),
        "peak_kwh": round(peak.energy_kwh, 3),
        "peak_timestamp": peak.timestamp.isoformat(),
        "points": [{"timestamp": r.timestamp.isoformat(), "energy_kwh": r.energy_kwh} for r in readings],
    }


def device_wise_breakdown(db: Session, building_id: int | None, days: int = 30) -> list[dict]:
    cutoff = datetime.utcnow() - timedelta(days=days)
    q = db.query(
        models.Device.id, models.Device.name, models.Device.device_type,
        func.sum(models.EnergyReading.energy_kwh).label("total_kwh"),
        func.avg(models.EnergyReading.energy_kwh).label("avg_kwh"),
        func.max(models.EnergyReading.energy_kwh).label("peak_kwh"),
        func.count(models.EnergyReading.id).label("reading_count"),
    ).join(models.EnergyReading, models.EnergyReading.device_id == models.Device.id) \
     .filter(models.EnergyReading.timestamp >= cutoff)

    if building_id:
        q = q.filter(models.Device.building_id == building_id)

    q = q.group_by(models.Device.id, models.Device.name, models.Device.device_type)
    rows = q.all()
    return [
        {
            "device_id": r.id,
            "device_name": r.name,
            "device_type": r.device_type,
            "total_kwh": round(r.total_kwh or 0, 2),
            "avg_kwh": round(r.avg_kwh or 0, 3),
            "peak_kwh": round(r.peak_kwh or 0, 3),
            "reading_count": r.reading_count,
        }
        for r in rows
    ]


def forecast_accuracy_history(db: Session, device_id: int | None, building_id: int | None, limit: int = 20) -> list[dict]:
    q = db.query(models.ForecastRun)
    if device_id:
        q = q.filter(models.ForecastRun.device_id == device_id)
    elif building_id:
        q = q.filter(models.ForecastRun.building_id == building_id)
    runs = q.order_by(models.ForecastRun.created_at.desc()).limit(limit).all()
    return [
        {
            "run_id": r.id,
            "model_used": r.model_used,
            "granularity": r.granularity,
            "horizon": r.horizon,
            "mae": r.mae,
            "rmse": r.rmse,
            "mape": r.mape,
            "created_at": r.created_at.isoformat(),
        }
        for r in runs
    ]


def recent_alerts(db: Session, device_id: int | None, building_id: int | None, limit: int = 20) -> list[dict]:
    q = db.query(models.Alert)
    if device_id:
        q = q.filter(models.Alert.device_id == device_id)
    elif building_id:
        q = q.filter(models.Alert.building_id == building_id)
    alerts = q.order_by(models.Alert.created_at.desc()).limit(limit).all()
    return [
        {
            "id": a.id,
            "alert_type": a.alert_type,
            "message": a.message,
            "severity": a.severity,
            "window_start": a.window_start.isoformat() if a.window_start else None,
            "window_end": a.window_end.isoformat() if a.window_end else None,
            "created_at": a.created_at.isoformat(),
            "acknowledged": a.acknowledged,
        }
        for a in alerts
    ]


def dashboard_overview(db: Session) -> dict:
    buildings = db.query(models.Building).count()
    devices = db.query(models.Device).count()
    readings = db.query(models.EnergyReading).count()
    anomalies_7d = db.query(models.AnomalyRecord).filter(
        models.AnomalyRecord.timestamp >= datetime.utcnow() - timedelta(days=7)
    ).count()
    open_alerts = db.query(models.Alert).filter(models.Alert.acknowledged == False).count()  # noqa: E712
    return {
        "buildings": buildings,
        "devices": devices,
        "total_readings": readings,
        "anomalies_last_7d": anomalies_7d,
        "open_alerts": open_alerts,
    }
