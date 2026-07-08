from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.services import analytics_service

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/overview")
def overview(db: Session = Depends(get_db)):
    return analytics_service.dashboard_overview(db)


@router.get("/historical")
def historical(device_id: int | None = None, building_id: int | None = None, days: int = 30, db: Session = Depends(get_db)):
    return analytics_service.historical_summary(db, device_id, building_id, days)


@router.get("/device-breakdown")
def device_breakdown(building_id: int | None = None, days: int = 30, db: Session = Depends(get_db)):
    return analytics_service.device_wise_breakdown(db, building_id, days)


@router.get("/forecast-accuracy")
def forecast_accuracy(device_id: int | None = None, building_id: int | None = None, db: Session = Depends(get_db)):
    return analytics_service.forecast_accuracy_history(db, device_id, building_id)


@router.get("/alerts")
def alerts(device_id: int | None = None, building_id: int | None = None, db: Session = Depends(get_db)):
    return analytics_service.recent_alerts(db, device_id, building_id)
