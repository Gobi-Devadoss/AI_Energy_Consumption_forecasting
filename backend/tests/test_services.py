import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from app.ml import preprocessing
from app.services import anomaly_service, optimization_service, simulation_service
from app.schemas.simulation import SimulationRequest


def _sample_df(hours=200, with_gaps=False, with_spike=False):
    start = datetime(2026, 1, 1)
    idx = [start + timedelta(hours=i) for i in range(hours)]
    rng = np.random.default_rng(0)
    base = 5 + 3 * np.sin(np.linspace(0, 20 * np.pi, hours)) + rng.normal(0, 0.3, hours)
    base = np.clip(base, 0.1, None)
    if with_spike:
        base[50] = base[50] * 5
    df = pd.DataFrame({"timestamp": idx, "energy_kwh": base, "temperature_c": 25.0, "occupancy": 0.5})
    if with_gaps:
        df = df.drop(df.index[10:13])
    return df


def test_regularize_hourly_fills_gaps():
    df = _sample_df(hours=100, with_gaps=True)
    out = preprocessing.regularize_hourly(df)
    # should be back to a continuous hourly index with no NaNs
    assert out["energy_kwh"].isna().sum() == 0
    assert out["is_interpolated"].sum() >= 1


def test_remove_extreme_outliers_caps_spike():
    df = _sample_df(hours=200, with_spike=True)
    cleaned = preprocessing.remove_extreme_outliers_for_training(df)
    assert cleaned["energy_kwh"].max() < df["energy_kwh"].max()


def test_add_time_features():
    df = _sample_df(hours=50)
    out = preprocessing.add_time_features(df)
    for col in ["hour_sin", "hour_cos", "dow_sin", "dow_cos", "is_weekend"]:
        assert col in out.columns


def test_train_test_split_chronological():
    df = _sample_df(hours=100)
    train, test = preprocessing.train_test_split_series(df)
    assert train["timestamp"].max() < test["timestamp"].min()
    assert len(train) + len(test) == len(df)


def test_anomaly_detect_zscore_finds_spike():
    df = _sample_df(hours=300, with_spike=True)
    flagged = anomaly_service.detect(df, method="zscore")
    assert len(flagged) >= 1
    assert flagged["timestamp"].isin([df.loc[50, "timestamp"]]).any()


def test_anomaly_detect_threshold_flags_over_capacity():
    df = _sample_df(hours=50)
    df.loc[5, "energy_kwh"] = 999  # way beyond any reasonable capacity
    flagged = anomaly_service.detect(df, method="threshold", rated_capacity_kw=10.0)
    assert len(flagged) == 1
    assert flagged.iloc[0]["severity"] in ("medium", "high")


def test_optimization_recommendations_generate_for_concentrated_load():
    hours = 240
    start = datetime(2026, 1, 1)
    idx = [start + timedelta(hours=i) for i in range(hours)]
    vals = []
    for ts in idx:
        vals.append(20.0 if ts.hour in (18, 19, 20) else 1.0)
    df = pd.DataFrame({"timestamp": idx, "energy_kwh": vals})
    recs = optimization_service.generate_recommendations(df, "Test-Device")
    assert len(recs) >= 1
    assert any(r["category"] == "load_balancing" for r in recs)


def test_simulation_device_shutdown_reduces_usage():
    df = _sample_df(hours=240)
    req = SimulationRequest(scenario_type="device_shutdown", shutdown_hours=[0, 1, 2], device_id=1)
    result = simulation_service.run_simulation(df, "device_shutdown", req)
    assert result["projected_kwh"] < result["baseline_kwh"]
    assert result["savings_kwh"] > 0


def test_simulation_peak_hour_reduction():
    df = _sample_df(hours=240)
    req = SimulationRequest(scenario_type="peak_hour_reduction", peak_reduction_pct=20, device_id=1)
    result = simulation_service.run_simulation(df, "peak_hour_reduction", req)
    assert result["savings_pct"] > 0


def test_simulation_temperature_increase_raises_usage():
    df = _sample_df(hours=240)
    req = SimulationRequest(scenario_type="temperature_change", temperature_change_c=5, device_id=1)
    result = simulation_service.run_simulation(df, "temperature_change", req)
    assert result["projected_kwh"] > result["baseline_kwh"]
