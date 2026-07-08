"""
Dataset ingestion layer.

Expected CSV columns (case-insensitive, flexible order):
    timestamp        (required)  - any pandas-parseable datetime
    device_id         (required)  - external device identifier, string
    building           (optional)  - building name, defaults to "Default Building"
    energy_kwh        (required)  - numeric usage
    temperature_c    (optional)
    occupancy          (optional)
    device_type       (optional)
    rated_capacity_kw (optional)

Handles the required edge cases explicitly:
    - Missing timestamps          -> rows dropped with a warning, never silently invented at ingest time
                                       (interpolation happens later, at read-time, in ml/preprocessing)
    - Sparse sensor data           -> accepted as-is; regularization happens downstream per-device
    - Sudden spikes                -> NOT filtered here (anomaly detection needs to see them);
                                       only physically impossible values (negative energy) are rejected
    - Invalid uploads               -> missing required columns / unparseable file raises ValueError with
                                       a clear message the API layer turns into HTTP 400
"""
from __future__ import annotations
import pandas as pd
import numpy as np
import uuid
from io import BytesIO
from sqlalchemy.orm import Session
from app.db import models

REQUIRED_COLUMNS = {"timestamp", "device_id", "energy_kwh"}
COLUMN_ALIASES = {
    "device": "device_id",
    "deviceid": "device_id",
    "device_name": "device_id",
    "energy": "energy_kwh",
    "usage_kwh": "energy_kwh",
    "kwh": "energy_kwh",
    "temp": "temperature_c",
    "temperature": "temperature_c",
    "building_name": "building",
}


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    df = df.rename(columns={k: v for k, v in COLUMN_ALIASES.items() if k in df.columns})
    return df


def parse_upload(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """Parse raw upload bytes into a validated DataFrame. Raises ValueError on invalid uploads."""
    try:
        if filename.lower().endswith(".json"):
            df = pd.read_json(BytesIO(file_bytes))
        else:
            df = pd.read_csv(BytesIO(file_bytes))
    except Exception as e:
        raise ValueError(f"Could not parse uploaded file - ensure it is a valid CSV/JSON. ({e})")

    if df.empty:
        raise ValueError("Uploaded file contains no rows")

    df = _normalize_columns(df)

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(
            f"Uploaded file is missing required column(s): {sorted(missing)}. "
            f"Required columns are: {sorted(REQUIRED_COLUMNS)}"
        )

    return df


def ingest_dataframe(db: Session, df: pd.DataFrame) -> dict:
    """
    Validate row-by-row, create/lookup Building & Device rows, and bulk-insert
    EnergyReading rows. Returns an UploadSummary-shaped dict.
    """
    batch_id = str(uuid.uuid4())[:8]
    warnings: list[str] = []
    rows_rejected = 0

    df = df.copy()

    # --- Missing timestamps: drop unparseable / null timestamps ---
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    bad_ts = df["timestamp"].isna()
    if bad_ts.any():
        warnings.append(f"{int(bad_ts.sum())} row(s) dropped due to missing/invalid timestamp")
        rows_rejected += int(bad_ts.sum())
        df = df[~bad_ts]

    # --- energy_kwh must be numeric and non-negative (negative = sensor fault, physically invalid) ---
    df["energy_kwh"] = pd.to_numeric(df["energy_kwh"], errors="coerce")
    bad_energy = df["energy_kwh"].isna() | (df["energy_kwh"] < 0)
    if bad_energy.any():
        warnings.append(f"{int(bad_energy.sum())} row(s) dropped due to missing/negative energy_kwh")
        rows_rejected += int(bad_energy.sum())
        df = df[~bad_energy]

    if df.empty:
        raise ValueError("No valid rows remained after validation - please check the file format")

    df["device_id"] = df["device_id"].astype(str).str.strip()
    if "building" not in df.columns:
        df["building"] = "Default Building"
    df["building"] = df["building"].fillna("Default Building").astype(str).str.strip()
    df["building"] = df["building"].replace("", "Default Building")

    for optional_col in ["temperature_c", "occupancy", "device_type", "rated_capacity_kw"]:
        if optional_col not in df.columns:
            df[optional_col] = None

    buildings_created = 0
    devices_created = 0
    building_cache: dict[str, models.Building] = {}
    device_cache: dict[tuple, models.Device] = {}

    for b_name in df["building"].unique():
        building = db.query(models.Building).filter(models.Building.name == b_name).first()
        if not building:
            building = models.Building(name=b_name)
            db.add(building)
            db.flush()
            buildings_created += 1
        building_cache[b_name] = building

    device_groups = df[["building", "device_id", "device_type", "rated_capacity_kw"]].drop_duplicates(subset=["building", "device_id"])
    for _, row in device_groups.iterrows():
        key = (row["building"], row["device_id"])
        building = building_cache[row["building"]]
        device = db.query(models.Device).filter(
            models.Device.building_id == building.id,
            models.Device.external_id == row["device_id"],
        ).first()
        if not device:
            capacity = row["rated_capacity_kw"]
            try:
                capacity = float(capacity) if capacity is not None and not pd.isna(capacity) else None
            except (ValueError, TypeError):
                capacity = None
            device = models.Device(
                building_id=building.id,
                external_id=row["device_id"],
                name=row["device_id"],
                device_type=row["device_type"] if pd.notna(row["device_type"]) else None,
                rated_capacity_kw=capacity,
            )
            db.add(device)
            db.flush()
            devices_created += 1
        device_cache[key] = device

    readings = []
    for _, row in df.iterrows():
        device = device_cache[(row["building"], row["device_id"])]
        readings.append(models.EnergyReading(
            device_id=device.id,
            timestamp=row["timestamp"].to_pydatetime(),
            energy_kwh=float(row["energy_kwh"]),
            temperature_c=float(row["temperature_c"]) if pd.notna(row["temperature_c"]) else None,
            occupancy=float(row["occupancy"]) if pd.notna(row["occupancy"]) else None,
            source_batch=batch_id,
        ))

    db.bulk_save_objects(readings)
    db.commit()

    return {
        "batch_id": batch_id,
        "rows_ingested": len(readings),
        "rows_rejected": rows_rejected,
        "buildings_created": buildings_created,
        "devices_created": devices_created,
        "date_range_start": df["timestamp"].min().to_pydatetime() if not df.empty else None,
        "date_range_end": df["timestamp"].max().to_pydatetime() if not df.empty else None,
        "warnings": warnings,
    }


def get_device_readings(db: Session, device_id: int, lookback_days: int | None = None):
    q = db.query(models.EnergyReading).filter(models.EnergyReading.device_id == device_id)
    if lookback_days:
        from datetime import datetime, timedelta
        cutoff = datetime.utcnow() - timedelta(days=lookback_days)
        q = q.filter(models.EnergyReading.timestamp >= cutoff)
    return q.order_by(models.EnergyReading.timestamp).all()


def get_building_readings(db: Session, building_id: int, lookback_days: int | None = None):
    device_ids = [d.id for d in db.query(models.Device).filter(models.Device.building_id == building_id).all()]
    if not device_ids:
        return []
    q = db.query(models.EnergyReading).filter(models.EnergyReading.device_id.in_(device_ids))
    if lookback_days:
        from datetime import datetime, timedelta
        cutoff = datetime.utcnow() - timedelta(days=lookback_days)
        q = q.filter(models.EnergyReading.timestamp >= cutoff)
    return q.order_by(models.EnergyReading.timestamp).all()
