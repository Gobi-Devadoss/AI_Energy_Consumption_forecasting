"""
Forecasting layer.

Model strategy (per assignment: Prophet primary, LSTM as alt model):
    - "prophet"     : Prophet with daily/weekly seasonality (default/primary)
    - "lstm"        : windowed LSTM, used when the caller explicitly asks for
                       it or when Prophet is unavailable
    - "arima"       : statsmodels SARIMAX, lightweight statistical fallback
    - "regression"  : GradientBoosting on cyclical time features, the final
                       fallback that always works even on very short series
    - "auto"        : tries Prophet -> LSTM -> ARIMA -> regression, in that
                       order, until one trains successfully

This module is intentionally decoupled from FastAPI/SQLAlchemy request
objects - it only deals with pandas DataFrames and plain Python, so it can be
unit tested or reused by a batch/cron job.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from datetime import timedelta
from typing import Optional

from app.ml.preprocessing import (
    remove_extreme_outliers_for_training, add_time_features, train_test_split_series,
    readings_to_frame, regularize_hourly, aggregate_daily,
)
from app.core.config import settings


def load_series(db, device_id: int | None, building_id: int | None, granularity: str, lookback_days: int | None = None) -> pd.DataFrame:
    """
    Fetch raw readings for a device (or every device in a building, aggregated)
    and return a clean, regularly-spaced series at the requested granularity.
    """
    from app.services import data_service

    if device_id:
        readings = data_service.get_device_readings(db, device_id, lookback_days)
        raw = readings_to_frame(readings)
        hourly = regularize_hourly(raw)
    elif building_id:
        readings = data_service.get_building_readings(db, building_id, lookback_days)
        raw = readings_to_frame(readings)
        # multiple devices share timestamps - sum energy across devices per hour
        if not raw.empty:
            hourly = raw.groupby("timestamp", as_index=False).agg({
                "energy_kwh": "sum", "temperature_c": "mean", "occupancy": "mean"
            })
            hourly = regularize_hourly(hourly)
        else:
            hourly = raw
    else:
        raise ValueError("Either device_id or building_id must be provided")

    if granularity == "daily":
        return aggregate_daily(hourly)
    return hourly


HORIZON_STEPS_HOURLY = {"24h": 24, "7d": 24 * 7, "30d": 24 * 30}
HORIZON_STEPS_DAILY = {"24h": 1, "7d": 7, "30d": 30}


def _metrics(actual: np.ndarray, predicted: np.ndarray) -> dict:
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    if len(actual) == 0:
        return {"mae": None, "rmse": None, "mape": None}
    mae = float(np.mean(np.abs(actual - predicted)))
    rmse = float(np.sqrt(np.mean((actual - predicted) ** 2)))
    nonzero = actual != 0
    mape = float(np.mean(np.abs((actual[nonzero] - predicted[nonzero]) / actual[nonzero])) * 100) if nonzero.any() else None
    return {"mae": round(mae, 4), "rmse": round(rmse, 4), "mape": round(mape, 2) if mape is not None else None}


def _forecast_prophet(train_df: pd.DataFrame, steps: int, freq: str) -> tuple[pd.DataFrame, object]:
    from prophet import Prophet
    p = train_df.rename(columns={"timestamp": "ds", "energy_kwh": "y"})[["ds", "y"]]
    model = Prophet(
        daily_seasonality=True,
        weekly_seasonality=True,
        yearly_seasonality=False,
        interval_width=0.9,
    )
    model.fit(p)
    future = model.make_future_dataframe(periods=steps, freq=freq, include_history=False)
    fcst = model.predict(future)
    out = fcst[["ds", "yhat", "yhat_lower", "yhat_upper"]].rename(
        columns={"ds": "timestamp", "yhat": "predicted_kwh", "yhat_lower": "lower_bound", "yhat_upper": "upper_bound"}
    )
    out["predicted_kwh"] = out["predicted_kwh"].clip(lower=0)
    out["lower_bound"] = out["lower_bound"].clip(lower=0)
    return out, model


def _forecast_lstm(train_df: pd.DataFrame, steps: int, freq: str) -> pd.DataFrame:
    from app.ml.lstm_model import LSTMForecaster, TF_AVAILABLE
    if not TF_AVAILABLE:
        raise RuntimeError("TensorFlow not available")
    series = train_df["energy_kwh"].values
    forecaster = LSTMForecaster().fit(series, epochs=20)
    preds = forecaster.forecast(steps)
    last_ts = train_df["timestamp"].max()
    idx = pd.date_range(last_ts + pd.tseries.frequencies.to_offset(freq), periods=steps, freq=freq)
    spread = float(np.std(series)) * 0.5
    return pd.DataFrame({
        "timestamp": idx,
        "predicted_kwh": np.clip(preds, 0, None),
        "lower_bound": np.clip(preds - spread, 0, None),
        "upper_bound": preds + spread,
    })


def _forecast_arima(train_df: pd.DataFrame, steps: int, freq: str) -> pd.DataFrame:
    from statsmodels.tsa.statespace.sarimax import SARIMAX
    series = train_df.set_index("timestamp")["energy_kwh"].asfreq(freq)
    series = series.interpolate().bfill()
    seasonal_period = 24 if freq == "h" else 7
    model = SARIMAX(
        series, order=(2, 1, 2), seasonal_order=(1, 0, 1, seasonal_period),
        enforce_stationarity=False, enforce_invertibility=False,
    )
    fitted = model.fit(disp=False)
    forecast_res = fitted.get_forecast(steps=steps)
    mean = forecast_res.predicted_mean
    ci = forecast_res.conf_int(alpha=0.1)
    idx = pd.date_range(series.index.max() + pd.tseries.frequencies.to_offset(freq), periods=steps, freq=freq)
    return pd.DataFrame({
        "timestamp": idx,
        "predicted_kwh": np.clip(mean.values, 0, None),
        "lower_bound": np.clip(ci.iloc[:, 0].values, 0, None),
        "upper_bound": ci.iloc[:, 1].values,
    })


def _forecast_regression(train_df: pd.DataFrame, steps: int, freq: str) -> pd.DataFrame:
    from sklearn.ensemble import GradientBoostingRegressor
    feat = add_time_features(train_df)
    feature_cols = ["hour_sin", "hour_cos", "dow_sin", "dow_cos", "is_weekend", "month"]
    model = GradientBoostingRegressor(random_state=42, n_estimators=200, max_depth=3)
    model.fit(feat[feature_cols], feat["energy_kwh"])

    last_ts = train_df["timestamp"].max()
    idx = pd.date_range(last_ts + pd.tseries.frequencies.to_offset(freq), periods=steps, freq=freq)
    future = add_time_features(pd.DataFrame({"timestamp": idx}))
    preds = model.predict(future[feature_cols])
    resid_std = float(np.std(feat["energy_kwh"] - model.predict(feat[feature_cols])))
    return pd.DataFrame({
        "timestamp": idx,
        "predicted_kwh": np.clip(preds, 0, None),
        "lower_bound": np.clip(preds - resid_std, 0, None),
        "upper_bound": preds + resid_std,
    })


MODEL_FUNCS = {
    "prophet": _forecast_prophet,
    "lstm": _forecast_lstm,
    "arima": _forecast_arima,
    "regression": _forecast_regression,
}


def run_forecast(
    df: pd.DataFrame,
    horizon: str,
    granularity: str,
    model_choice: str = "auto",
) -> dict:
    """
    df: cleaned dataframe with columns [timestamp, energy_kwh] (already
        regularized/aggregated to the requested granularity by the caller).
    Returns dict with keys: model_used, points(DataFrame), metrics(dict)
    """
    if df.empty or len(df) < 8:
        raise ValueError("Not enough historical data to generate a forecast (need at least 8 points)")

    freq = "h" if granularity == "hourly" else "D"
    steps = (HORIZON_STEPS_HOURLY if granularity == "hourly" else HORIZON_STEPS_DAILY)[horizon]

    clean_df = remove_extreme_outliers_for_training(df)
    train_df, test_df = train_test_split_series(clean_df)

    order = ["prophet", "lstm", "arima", "regression"] if model_choice == "auto" else [model_choice]
    last_error = None

    for candidate in order:
        try:
            func = MODEL_FUNCS[candidate]
            # backtest on held-out tail (if any) for accuracy metrics
            metrics = {"mae": None, "rmse": None, "mape": None}
            if len(test_df) > 0:
                try:
                    if candidate == "prophet":
                        bt_points, _ = func(train_df, len(test_df), freq)
                    else:
                        bt_points = func(train_df, len(test_df), freq)
                    merged = test_df.merge(bt_points, on="timestamp", how="inner")
                    if len(merged) > 0:
                        metrics = _metrics(merged["energy_kwh"], merged["predicted_kwh"])
                except Exception:
                    pass  # backtest failure shouldn't block the actual forecast

            # full-horizon forecast trained on all available data
            if candidate == "prophet":
                points, _ = func(clean_df, steps, freq)
            else:
                points = func(clean_df, steps, freq)

            return {"model_used": candidate, "points": points, "metrics": metrics}
        except Exception as e:  # noqa: BLE001
            last_error = e
            continue

    raise RuntimeError(f"All forecasting models failed. Last error: {last_error}")


def flag_peaks(points: pd.DataFrame, top_fraction: float = 0.15) -> pd.DataFrame:
    """Mark the top-N% predicted values as peak points and merge into contiguous windows."""
    if points.empty:
        return points
    out = points.copy()
    threshold = out["predicted_kwh"].quantile(1 - top_fraction)
    out["is_peak"] = out["predicted_kwh"] >= threshold
    return out


def peak_windows(points: pd.DataFrame) -> list[dict]:
    """Collapse consecutive is_peak rows into human-readable windows with alert text."""
    if points.empty or "is_peak" not in points:
        return []
    windows = []
    in_window = False
    start = None
    peak_val = 0.0
    for _, row in points.sort_values("timestamp").iterrows():
        if row["is_peak"] and not in_window:
            in_window = True
            start = row["timestamp"]
            peak_val = row["predicted_kwh"]
        elif row["is_peak"] and in_window:
            peak_val = max(peak_val, row["predicted_kwh"])
        elif not row["is_peak"] and in_window:
            in_window = False
            end = prev_ts
            windows.append({
                "start": start.isoformat(),
                "end": end.isoformat(),
                "peak_kwh": round(float(peak_val), 3),
                "message": f"Expected peak consumption between {start.strftime('%I %p')} and {end.strftime('%I %p')} on {start.strftime('%b %d')}",
            })
        prev_ts = row["timestamp"]
    if in_window:
        windows.append({
            "start": start.isoformat(),
            "end": prev_ts.isoformat(),
            "peak_kwh": round(float(peak_val), 3),
            "message": f"Expected peak consumption between {start.strftime('%I %p')} and {prev_ts.strftime('%I %p')} on {start.strftime('%b %d')}",
        })
    return windows
