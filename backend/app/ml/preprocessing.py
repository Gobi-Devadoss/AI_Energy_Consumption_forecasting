"""
Shared preprocessing / feature engineering utilities used by every ML layer
(forecasting, anomaly detection, optimization, simulation).

Design goal: keep this the single place that knows how to turn a raw list of
(timestamp, energy_kwh) tuples into a clean, regularly-spaced pandas Series,
so every downstream model sees consistent input regardless of how messy the
source data was (missing timestamps, sparse sensors, duplicate rows).
"""
from __future__ import annotations
import pandas as pd
import numpy as np
from typing import Optional


def readings_to_frame(readings: list) -> pd.DataFrame:
    """Convert a list of EnergyReading ORM rows into a tidy DataFrame."""
    if not readings:
        return pd.DataFrame(columns=["timestamp", "energy_kwh", "temperature_c", "occupancy"])
    df = pd.DataFrame([{
        "timestamp": r.timestamp,
        "energy_kwh": r.energy_kwh,
        "temperature_c": r.temperature_c,
        "occupancy": r.occupancy,
    } for r in readings])
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").drop_duplicates(subset="timestamp", keep="last")
    return df.reset_index(drop=True)


def regularize_hourly(df: pd.DataFrame, fill_limit: int = 6) -> pd.DataFrame:
    """
    Reindex a timestamped DataFrame onto a strictly-hourly grid.

    Handles two of the required edge cases directly:
      - Missing timestamps: reindexed and linearly interpolated (capped at
        `fill_limit` consecutive hours to avoid inventing long fake stretches).
      - Sparse sensor data: short gaps interpolated, long gaps left as NaN
        and then dropped, so models never train on fabricated data.
    """
    if df.empty:
        return df

    df = df.set_index("timestamp")
    full_index = pd.date_range(df.index.min(), df.index.max(), freq="h")
    df = df.reindex(full_index)
    df.index.name = "timestamp"

    df["is_interpolated"] = df["energy_kwh"].isna()
    df["energy_kwh"] = df["energy_kwh"].interpolate(method="linear", limit=fill_limit)
    df["temperature_c"] = df["temperature_c"].interpolate(method="linear", limit=fill_limit * 2)
    df["occupancy"] = df["occupancy"].interpolate(method="linear", limit=fill_limit * 2)

    # Drop rows where the gap was too long to safely interpolate
    df = df.dropna(subset=["energy_kwh"])
    return df.reset_index()


def aggregate_daily(df_hourly: pd.DataFrame) -> pd.DataFrame:
    """Roll an hourly frame up to daily totals."""
    if df_hourly.empty:
        return df_hourly
    tmp = df_hourly.set_index("timestamp")
    daily = tmp["energy_kwh"].resample("D").sum().to_frame()
    if "temperature_c" in tmp:
        daily["temperature_c"] = tmp["temperature_c"].resample("D").mean()
    if "occupancy" in tmp:
        daily["occupancy"] = tmp["occupancy"].resample("D").mean()
    return daily.reset_index()


def add_time_features(df: pd.DataFrame, ts_col: str = "timestamp") -> pd.DataFrame:
    """Cyclical + calendar features used by the regression fallback model."""
    out = df.copy()
    out["hour"] = out[ts_col].dt.hour
    out["dow"] = out[ts_col].dt.dayofweek
    out["is_weekend"] = (out["dow"] >= 5).astype(int)
    out["month"] = out[ts_col].dt.month
    out["hour_sin"] = np.sin(2 * np.pi * out["hour"] / 24)
    out["hour_cos"] = np.cos(2 * np.pi * out["hour"] / 24)
    out["dow_sin"] = np.sin(2 * np.pi * out["dow"] / 7)
    out["dow_cos"] = np.cos(2 * np.pi * out["dow"] / 7)
    return out


def remove_extreme_outliers_for_training(df: pd.DataFrame, z_thresh: float = 5.0) -> pd.DataFrame:
    """
    Winsorize sudden spikes before model *training* only (never before anomaly
    detection, which needs to see the real spikes). Prevents one faulty sensor
    reading from dragging an entire forecast off course.
    """
    if df.empty or len(df) < 10:
        return df
    vals = df["energy_kwh"]
    mean, std = vals.mean(), vals.std()
    if std == 0 or np.isnan(std):
        return df
    z = (vals - mean) / std
    cleaned = df.copy()
    cap_hi = mean + z_thresh * std
    cap_lo = max(0.0, mean - z_thresh * std)
    cleaned.loc[z.abs() > z_thresh, "energy_kwh"] = cleaned.loc[z.abs() > z_thresh, "energy_kwh"].clip(cap_lo, cap_hi)
    return cleaned


def train_test_split_series(df: pd.DataFrame, test_fraction: float = 0.15, min_test: int = 6) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Chronological split (never shuffle time series) for accuracy metrics."""
    n = len(df)
    n_test = max(min_test, int(n * test_fraction))
    n_test = min(n_test, n - 5) if n > 10 else 0
    if n_test <= 0:
        return df, df.iloc[0:0]
    return df.iloc[:-n_test], df.iloc[-n_test:]
