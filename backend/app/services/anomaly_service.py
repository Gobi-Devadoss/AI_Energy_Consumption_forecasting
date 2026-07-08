"""
Anomaly detection layer.

Combines three complementary techniques so different failure modes get
caught:
    - Isolation Forest : multivariate, catches contextual anomalies (e.g. a
                          normal-looking value at an abnormal hour/temperature
                          combination) - good for "unexpected night-time usage".
    - Z-score           : fast univariate statistical outlier check - good for
                          "sudden energy spikes".
    - Threshold rule    : device-capacity-aware hard ceiling - good for
                          "faulty device / sensor anomalies" that exceed what's
                          physically plausible for that device.

`detect` runs all three and de-duplicates, tagging each anomaly with the
method(s) that flagged it and a severity derived from how far outside normal
range the point is.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from app.core.config import settings


def _isolation_forest_flags(df: pd.DataFrame) -> pd.Series:
    from sklearn.ensemble import IsolationForest
    if len(df) < 20:
        return pd.Series([False] * len(df), index=df.index)

    feat = df.copy()
    feat["hour"] = feat["timestamp"].dt.hour
    feat["dow"] = feat["timestamp"].dt.dayofweek
    X = feat[["energy_kwh", "hour", "dow"]].fillna(feat[["energy_kwh", "hour", "dow"]].mean())

    model = IsolationForest(
        contamination=settings.isolation_forest_contamination,
        random_state=42,
        n_estimators=150,
    )
    preds = model.fit_predict(X)
    scores = model.decision_function(X)
    df_flags = pd.Series(preds == -1, index=df.index)
    return df_flags, pd.Series(scores, index=df.index)


def _zscore_flags(df: pd.DataFrame, threshold: float | None = None) -> tuple[pd.Series, pd.Series]:
    threshold = threshold or settings.zscore_threshold
    vals = df["energy_kwh"]
    mean, std = vals.mean(), vals.std()
    if std == 0 or np.isnan(std):
        return pd.Series([False] * len(df), index=df.index), pd.Series([0.0] * len(df), index=df.index)
    z = (vals - mean) / std
    return z.abs() > threshold, z


def _threshold_flags(df: pd.DataFrame, rated_capacity_kw: float | None) -> pd.Series:
    if not rated_capacity_kw or rated_capacity_kw <= 0:
        return pd.Series([False] * len(df), index=df.index)
    # An hourly reading physically cannot exceed rated capacity (kWh in 1h == kW)
    # allow 10% headroom for measurement noise
    return df["energy_kwh"] > (rated_capacity_kw * 1.10)


def _severity(z_abs: float) -> str:
    if z_abs >= 5:
        return "high"
    if z_abs >= 3.5:
        return "medium"
    return "low"


def detect(df: pd.DataFrame, method: str = "auto", rated_capacity_kw: float | None = None) -> pd.DataFrame:
    """
    df: dataframe with columns [timestamp, energy_kwh] (raw, NOT outlier-cleaned -
        anomaly detection must see the real spikes).
    Returns a dataframe of only the flagged rows with columns:
        timestamp, energy_kwh, method, severity, score, reason
    """
    if df.empty:
        return pd.DataFrame(columns=["timestamp", "energy_kwh", "method", "severity", "score", "reason"])

    df = df.reset_index(drop=True)
    results = []

    run_iso = method in ("auto", "isolation_forest")
    run_z = method in ("auto", "zscore")
    run_thresh = method in ("auto", "threshold")

    iso_flags, iso_scores = (pd.Series([False] * len(df)), pd.Series([0.0] * len(df)))
    if run_iso:
        try:
            iso_flags, iso_scores = _isolation_forest_flags(df)
        except Exception:
            pass

    z_flags, z_scores = _zscore_flags(df) if run_z else (pd.Series([False] * len(df)), pd.Series([0.0] * len(df)))
    thresh_flags = _threshold_flags(df, rated_capacity_kw) if run_thresh else pd.Series([False] * len(df))

    # night-time usage rule: flag meaningful usage between 1-4am that's well above the device's typical night baseline
    night_mask = df["timestamp"].dt.hour.isin([1, 2, 3, 4])
    night_baseline = df.loc[night_mask, "energy_kwh"].mean() if night_mask.any() else None
    unexpected_night = pd.Series([False] * len(df), index=df.index)
    if night_baseline is not None and not np.isnan(night_baseline):
        overall_mean = df["energy_kwh"].mean()
        if night_baseline < overall_mean * 0.5:  # nights are normally quiet
            unexpected_night = night_mask & (df["energy_kwh"] > night_baseline * 3 + 0.01)

    for i in df.index:
        reasons = []
        methods = []
        score = float(z_scores.iloc[i]) if len(z_scores) else 0.0

        if iso_flags.iloc[i] if len(iso_flags) else False:
            methods.append("isolation_forest")
            reasons.append("multivariate pattern deviates from normal usage context")
        if z_flags.iloc[i]:
            methods.append("zscore")
            reasons.append(f"{abs(score):.1f} standard deviations from mean")
        if thresh_flags.iloc[i]:
            methods.append("threshold")
            reasons.append("exceeds device rated capacity - possible sensor/device fault")
        if unexpected_night.iloc[i]:
            methods.append("night_pattern")
            reasons.append("unexpected night-time usage spike")

        if methods:
            results.append({
                "timestamp": df.loc[i, "timestamp"],
                "energy_kwh": df.loc[i, "energy_kwh"],
                "method": "+".join(sorted(set(methods))),
                "severity": _severity(abs(score)) if abs(score) > 0 else ("high" if thresh_flags.iloc[i] else "medium"),
                "score": round(score, 3),
                "reason": "; ".join(reasons),
            })

    return pd.DataFrame(results)
