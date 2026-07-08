"""
Automated retraining / rescan pipeline (bonus feature).

Runs on a schedule (default: every 6 hours) and, for every device with
enough history:
    1. regenerates the 24h forecast (keeps peak-alerts fresh)
    2. rescans for anomalies over the last 2 days

Designed to fail soft: any single device's failure is logged and skipped so
one bad series never blocks the rest of the fleet.
"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from app.db.database import SessionLocal
from app.db import models

logger = logging.getLogger("energy_platform.scheduler")
_scheduler: BackgroundScheduler | None = None


def _retrain_and_rescan_all():
    from app.services import forecasting_service, anomaly_service, data_service
    from app.ml.preprocessing import readings_to_frame
    from app.schemas.forecast import ForecastRequest
    from app.routers.forecast import _persist_forecast

    db = SessionLocal()
    try:
        devices = db.query(models.Device).all()
        for device in devices:
            try:
                df = forecasting_service.load_series(db, device.id, None, "hourly")
                if len(df) < 8:
                    continue
                result = forecasting_service.run_forecast(df, "24h", "hourly", "auto")
                req = ForecastRequest(device_id=device.id, horizon="24h", granularity="hourly", model="auto")
                _persist_forecast(db, req, result)
            except Exception as e:  # noqa: BLE001
                logger.warning("Scheduled forecast failed for device %s: %s", device.id, e)

            try:
                readings = data_service.get_device_readings(db, device.id, lookback_days=2)
                raw = readings_to_frame(readings)
                if raw.empty:
                    continue
                flagged = anomaly_service.detect(raw, method="auto", rated_capacity_kw=device.rated_capacity_kw)
                for _, row in flagged.iterrows():
                    exists = db.query(models.AnomalyRecord).filter(
                        models.AnomalyRecord.device_id == device.id,
                        models.AnomalyRecord.timestamp == row["timestamp"],
                    ).first()
                    if not exists:
                        db.add(models.AnomalyRecord(
                            device_id=device.id, timestamp=row["timestamp"], energy_kwh=row["energy_kwh"],
                            method=row["method"], severity=row["severity"], score=row["score"], reason=row["reason"],
                        ))
                db.commit()
            except Exception as e:  # noqa: BLE001
                logger.warning("Scheduled anomaly scan failed for device %s: %s", device.id, e)
    finally:
        db.close()


def start_scheduler():
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(_retrain_and_rescan_all, "interval", hours=6, id="retrain_rescan", next_run_time=None)
    _scheduler.start()
    logger.info("Background retraining/rescan scheduler started (every 6h)")


def shutdown_scheduler():
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
