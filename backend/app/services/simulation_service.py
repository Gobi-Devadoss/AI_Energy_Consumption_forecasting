"""
What-if scenario simulation.

Rather than a black-box model, each scenario applies a transparent,
explainable transformation to the historical baseline usage curve. This
keeps results auditable ("why did it say 12% savings?") which matters more
for a decision-support tool than marginal accuracy gains from a opaque model.
"""
from __future__ import annotations
import pandas as pd
import numpy as np
from app.core.config import settings

# Rough empirical sensitivities used for the occupancy/temperature scenarios.
# These are intentionally simple, well-documented coefficients rather than a
# trained model, since ground truth for "what if occupancy changes" isn't
# present in a typical smart-meter dataset.
OCCUPANCY_ENERGY_ELASTICITY = 0.55   # 1% occupancy change -> 0.55% energy change
TEMPERATURE_HVAC_SENSITIVITY = 0.04  # 1 degree C change -> 4% change in HVAC-relevant load


def _baseline_kwh(df: pd.DataFrame) -> float:
    return float(df["energy_kwh"].sum())


def simulate_occupancy_change(df: pd.DataFrame, occupancy_change_pct: float) -> tuple[float, float, str]:
    baseline = _baseline_kwh(df)
    factor = 1 + (occupancy_change_pct / 100.0) * OCCUPANCY_ENERGY_ELASTICITY
    projected = max(0.0, baseline * factor)
    explanation = (
        f"Applied an occupancy elasticity of {OCCUPANCY_ENERGY_ELASTICITY} (energy scales sub-linearly "
        f"with occupancy due to fixed baseline loads) to a {occupancy_change_pct:+.1f}% occupancy change."
    )
    return baseline, projected, explanation


def simulate_temperature_change(df: pd.DataFrame, temperature_change_c: float) -> tuple[float, float, str]:
    baseline = _baseline_kwh(df)
    factor = 1 + (temperature_change_c * TEMPERATURE_HVAC_SENSITIVITY)
    projected = max(0.0, baseline * factor)
    direction = "increase" if temperature_change_c > 0 else "decrease"
    explanation = (
        f"Assumed HVAC-relevant load scales at {TEMPERATURE_HVAC_SENSITIVITY*100:.0f}% per degree C. "
        f"A {abs(temperature_change_c):.1f}C {direction} projects a "
        f"{abs(factor-1)*100:.1f}% change in total consumption."
    )
    return baseline, projected, explanation


def simulate_device_shutdown(df: pd.DataFrame, shutdown_hours: list[int]) -> tuple[float, float, str]:
    baseline = _baseline_kwh(df)
    tmp = df.copy()
    tmp["hour"] = tmp["timestamp"].dt.hour
    removed = tmp[tmp["hour"].isin(shutdown_hours)]["energy_kwh"].sum()
    projected = max(0.0, baseline - removed)
    hour_str = ", ".join(f"{h}:00" for h in sorted(shutdown_hours))
    explanation = (
        f"Removed historical consumption recorded during the proposed shutdown hours ({hour_str}), "
        f"assuming the device is fully powered off during that window."
    )
    return baseline, projected, explanation


def simulate_peak_hour_reduction(df: pd.DataFrame, peak_reduction_pct: float) -> tuple[float, float, str]:
    baseline = _baseline_kwh(df)
    tmp = df.copy()
    tmp["hour"] = tmp["timestamp"].dt.hour
    profile = tmp.groupby("hour")["energy_kwh"].mean()
    peak_hours = profile.nlargest(max(1, int(len(profile) * 0.25))).index.tolist()
    peak_mask = tmp["hour"].isin(peak_hours)
    peak_total = tmp.loc[peak_mask, "energy_kwh"].sum()
    reduction = peak_total * (peak_reduction_pct / 100.0)
    projected = max(0.0, baseline - reduction)
    hour_str = ", ".join(f"{h}:00" for h in sorted(peak_hours))
    explanation = (
        f"Identified top usage hours ({hour_str}) as peak windows and applied a "
        f"{peak_reduction_pct:.0f}% load reduction to consumption within those hours only."
    )
    return baseline, projected, explanation


SCENARIO_FUNCS = {
    "occupancy_change": lambda df, p: simulate_occupancy_change(df, p.occupancy_change_pct or 0.0),
    "temperature_change": lambda df, p: simulate_temperature_change(df, p.temperature_change_c or 0.0),
    "device_shutdown": lambda df, p: simulate_device_shutdown(df, p.shutdown_hours or []),
    "peak_hour_reduction": lambda df, p: simulate_peak_hour_reduction(df, p.peak_reduction_pct or 10.0),
}


def run_simulation(df: pd.DataFrame, scenario_type: str, params) -> dict:
    if df.empty:
        raise ValueError("No historical data available for simulation")
    func = SCENARIO_FUNCS.get(scenario_type)
    if func is None:
        raise ValueError(f"Unknown scenario type: {scenario_type}")

    baseline, projected, explanation = func(df, params)
    savings_kwh = baseline - projected
    savings_pct = (savings_kwh / baseline * 100) if baseline > 0 else 0.0
    rate = params.electricity_rate_per_kwh or settings.default_electricity_rate_per_kwh
    cost_impact = savings_kwh * rate

    return {
        "baseline_kwh": round(baseline, 3),
        "projected_kwh": round(projected, 3),
        "savings_kwh": round(savings_kwh, 3),
        "savings_pct": round(savings_pct, 2),
        "cost_impact": round(cost_impact, 2),
        "currency_rate_used": rate,
        "explanation": explanation,
    }
