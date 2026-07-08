"""
Generates a realistic synthetic multi-building, multi-device hourly energy
dataset and writes it to CSV, then (optionally) ingests it straight into the
database. Useful for demoing the platform without needing a real smart-meter
export on hand.

Run directly:
    python -m app.utils.seed_data --days 90 --ingest
"""
from __future__ import annotations
import argparse
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

RNG = np.random.default_rng(42)

BUILDINGS = {
    "HQ Tower": [
        ("HVAC-01", "HVAC", 45.0),
        ("Lighting-01", "Lighting", 12.0),
        ("Server-Rack-01", "Server", 30.0),
        ("Elevator-01", "Elevator", 15.0),
    ],
    "Warehouse-A": [
        ("Compressor-01", "Compressor", 60.0),
        ("Lighting-02", "Lighting", 8.0),
        ("Conveyor-01", "Conveyor", 25.0),
    ],
    "R&D Lab": [
        ("HVAC-02", "HVAC", 35.0),
        ("Server-Rack-02", "Server", 50.0),
        ("Lab-Equipment-01", "Lab Equipment", 20.0),
    ],
}

# Base hourly shape (fraction of peak) - a typical commercial occupancy curve
BASE_SHAPE = np.array([
    0.25, 0.22, 0.20, 0.20, 0.22, 0.28,   # 00-05 night
    0.40, 0.65, 0.85, 0.95, 1.00, 0.98,   # 06-11 morning ramp
    0.90, 0.95, 0.97, 0.92, 0.88, 0.80,   # 12-17 afternoon
    0.60, 0.45, 0.38, 0.33, 0.30, 0.27,   # 18-23 evening wind-down
])


def _device_series(device_type: str, capacity_kw: float, hours: pd.DatetimeIndex) -> np.ndarray:
    shape = BASE_SHAPE.copy()
    if device_type in ("Server", "Lab Equipment"):
        # servers run flatter, near-constant load
        shape = 0.6 + 0.4 * shape
    if device_type == "Compressor":
        shape = np.clip(shape * 1.1, 0, 1)

    hour_of_day = hours.hour.values
    dow = hours.dayofweek.values
    weekend_factor = np.where(dow >= 5, 0.55 if device_type not in ("Server",) else 0.9, 1.0)

    base = shape[hour_of_day] * capacity_kw * 0.55 * weekend_factor
    noise = RNG.normal(0, capacity_kw * 0.03, size=len(hours))
    seasonal_drift = 1 + 0.05 * np.sin(2 * np.pi * hours.dayofyear.values / 365)
    series = np.clip(base * seasonal_drift + noise, 0.02 * capacity_kw, capacity_kw * 1.05)

    # inject occasional spikes (~0.5% of points) to give anomaly detection something to find
    spike_mask = RNG.random(len(hours)) < 0.005
    series[spike_mask] *= RNG.uniform(1.8, 2.6, size=spike_mask.sum())

    # inject a few faulty-sensor negative-adjacent dips (~0.2%)
    dip_mask = RNG.random(len(hours)) < 0.002
    series[dip_mask] *= RNG.uniform(0.05, 0.15, size=dip_mask.sum())

    return np.round(series, 3)


def generate(days: int = 90, end: datetime | None = None) -> pd.DataFrame:
    end = end or datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(days=days)
    hours = pd.date_range(start, end, freq="h")

    rows = []
    for building, devices in BUILDINGS.items():
        temp_base = 24 + 6 * np.sin(2 * np.pi * (hours.dayofyear.values - 172) / 365)
        temp_noise = RNG.normal(0, 1.5, size=len(hours))
        temperature = np.round(temp_base + temp_noise, 1)
        occupancy = np.clip(BASE_SHAPE[hours.hour.values] + RNG.normal(0, 0.05, len(hours)), 0, 1)

        for device_id, device_type, capacity in devices:
            energy = _device_series(device_type, capacity, hours)
            for i, ts in enumerate(hours):
                rows.append({
                    "timestamp": ts,
                    "building": building,
                    "device_id": device_id,
                    "device_type": device_type,
                    "rated_capacity_kw": capacity,
                    "energy_kwh": energy[i],
                    "temperature_c": temperature[i],
                    "occupancy": round(float(occupancy[i]), 3),
                })

    df = pd.DataFrame(rows)

    # simulate a few missing timestamps (sparse sensor data edge case)
    drop_idx = df.sample(frac=0.003, random_state=1).index
    df = df.drop(index=drop_idx)

    return df.sort_values(["building", "device_id", "timestamp"]).reset_index(drop=True)


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic energy dataset")
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--out", type=str, default="data/synthetic_energy_dataset.csv")
    parser.add_argument("--ingest", action="store_true", help="Ingest directly into the configured database")
    args = parser.parse_args()

    df = generate(days=args.days)
    df.to_csv(args.out, index=False)
    print(f"Wrote {len(df)} rows to {args.out}")

    if args.ingest:
        from app.db.database import SessionLocal, init_db
        from app.services import data_service
        init_db()
        db = SessionLocal()
        try:
            summary = data_service.ingest_dataframe(db, data_service.parse_upload(open(args.out, "rb").read(), args.out))
            print("Ingestion summary:", summary)
        finally:
            db.close()


if __name__ == "__main__":
    main()
