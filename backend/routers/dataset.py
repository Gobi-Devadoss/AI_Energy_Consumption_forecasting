from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from core.database import get_db
from model import models
from schemas.dataset import UploadSummary, BuildingOut, DeviceOut, ReadingOut
from services import data_service

router = APIRouter(prefix="/dataset", tags=["Dataset"])


@router.post("/upload", response_model=UploadSummary)
async def upload_dataset(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Upload a CSV/JSON energy dataset. Required columns: timestamp, device_id, energy_kwh.
    Optional: building, temperature_c, occupancy, device_type, rated_capacity_kw.
    """
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    try:
        df = data_service.parse_upload(content, file.filename)
        summary = data_service.ingest_dataframe(db, df)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return summary


@router.get("/buildings", response_model=list[BuildingOut])
def list_buildings(db: Session = Depends(get_db)):
    return db.query(models.Building).order_by(models.Building.name).all()


@router.get("/buildings/{building_id}/devices", response_model=list[DeviceOut])
def list_devices(building_id: int, db: Session = Depends(get_db)):
    devices = db.query(models.Device).filter(models.Device.building_id == building_id).all()
    if not devices:
        exists = db.query(models.Building).filter(models.Building.id == building_id).first()
        if not exists:
            raise HTTPException(status_code=404, detail="Building not found")
    return devices


@router.get("/devices", response_model=list[DeviceOut])
def list_all_devices(db: Session = Depends(get_db)):
    return db.query(models.Device).order_by(models.Device.name).all()


@router.get("/devices/{device_id}/readings", response_model=list[ReadingOut])
def device_readings(device_id: int, lookback_days: int = 30, db: Session = Depends(get_db)):
    device = db.query(models.Device).filter(models.Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    readings = data_service.get_device_readings(db, device_id, lookback_days)
    return readings
