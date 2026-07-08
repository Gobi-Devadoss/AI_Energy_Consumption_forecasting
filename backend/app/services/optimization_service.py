"""
Rule-driven optimization engine layered on top of the forecast + historical
statistics. Each rule inspects the hourly usage profile and, when its
trigger condition is met, emits a Recommendation-shaped dict. Kept as
composable small functions so new strategies can be added without touching
existing ones (open/closed).
"""
from __future__ import annotations
import pandas as pd
import numpy as np


def _hourly_profile(df: pd.DataFrame) -> pd.DataFrame:
    prof = df.copy()
    prof["hour"] = prof["timestamp"].dt.hour
    return prof.groupby("hour")["energy_kwh"].mean().reset_index()


def rule_load_balancing(df: pd.DataFrame, device_name: str) -> list[dict]:
    """If usage is heavily concentrated in a few hours, suggest spreading load."""
    profile = _hourly_profile(df)
    if profile.empty:
        return []
    total = profile["energy_kwh"].sum()
    if total <= 0:
        return []
    top3 = profile.nlargest(3, "energy_kwh")
    concentration = top3["energy_kwh"].sum() / total
    if concentration < 0.35:
        return []
    hours = sorted(top3["hour"].tolist())
    hour_str = ", ".join(f"{h}:00" for h in hours)
    savings_pct = round(min(concentration * 25, 18), 1)  # heuristic: balancing can shave up to ~18%
    return [{
        "category": "load_balancing",
        "title": f"Balance load away from peak hours ({hour_str})",
        "description": (
            f"{device_name} concentrates {concentration*100:.0f}% of its daily energy use in just "
            f"3 hours ({hour_str}). Spreading heavy or deferrable tasks across a wider window can "
            f"reduce peak-demand charges and transformer/circuit stress."
        ),
        "estimated_savings_kwh": round(total * (savings_pct / 100), 2),
        "estimated_savings_pct": savings_pct,
        "priority": "high" if concentration > 0.5 else "medium",
    }]


def rule_off_peak_shift(df: pd.DataFrame, device_name: str, peak_hours: list[int]) -> list[dict]:
    """Recommend shifting shiftable load to off-peak (typically cheaper) hours."""
    if not peak_hours:
        return []
    profile = _hourly_profile(df)
    if profile.empty:
        return []
    peak_usage = profile[profile["hour"].isin(peak_hours)]["energy_kwh"].sum()
    total = profile["energy_kwh"].sum()
    if total <= 0 or peak_usage / total < 0.25:
        return []
    off_peak_candidates = [h for h in range(24) if h not in peak_hours and (h < 6 or h > 22)]
    off_peak_str = ", ".join(f"{h}:00" for h in off_peak_candidates[:3]) or "late-night hours"
    savings_pct = round(min((peak_usage / total) * 20, 15), 1)
    return [{
        "category": "off_peak",
        "title": "Shift deferrable tasks to off-peak hours",
        "description": (
            f"Shift heavy or batchable processing tasks for {device_name} to off-peak hours such as "
            f"{off_peak_str}. This reduces exposure to peak-hour tariffs and eases grid demand during "
            f"high-load windows."
        ),
        "estimated_savings_kwh": round(peak_usage * (savings_pct / 100), 2),
        "estimated_savings_pct": savings_pct,
        "priority": "medium",
    }]


def rule_scheduling_hvac(df: pd.DataFrame, device_name: str, device_type: str | None, occupancy_col_present: bool) -> list[dict]:
    """HVAC/Lighting-specific: suggest reduced operation during predicted low occupancy."""
    if not device_type or device_type.lower() not in ("hvac", "lighting", "climate"):
        return []
    profile = _hourly_profile(df)
    if profile.empty:
        return []
    low_usage_hours = profile.nsmallest(6, "energy_kwh")["hour"].tolist()
    # low usage overnight/early morning already implies low occupancy for most commercial buildings
    quiet_hours = sorted([h for h in low_usage_hours if h < 7 or h >= 21])
    if not quiet_hours:
        return []
    hour_str = ", ".join(f"{h}:00" for h in quiet_hours)
    return [{
        "category": "scheduling",
        "title": f"Reduce {device_type} usage during low-occupancy hours",
        "description": (
            f"Historical patterns show minimal activity for {device_name} around {hour_str}. "
            f"Scheduling reduced HVAC/lighting setpoints or eco-mode during these hours can cut "
            f"energy waste without affecting comfort during occupied periods."
        ),
        "estimated_savings_kwh": None,
        "estimated_savings_pct": 8.0,
        "priority": "medium",
    }]


def rule_shutdown_recommendation(df: pd.DataFrame, device_name: str) -> list[dict]:
    """If a device shows near-zero but nonzero baseline usage overnight, flag phantom/standby load."""
    profile = _hourly_profile(df)
    if profile.empty:
        return []
    night = profile[(profile["hour"] >= 0) & (profile["hour"] <= 4)]
    day_avg = profile[(profile["hour"] >= 9) & (profile["hour"] <= 18)]["energy_kwh"].mean()
    night_avg = night["energy_kwh"].mean() if not night.empty else 0
    if day_avg and night_avg and 0 < night_avg < day_avg * 0.15 and night_avg > 0.05:
        annual_waste = night_avg * 5 * 365  # 5 idle hours/night, rough estimate
        return [{
            "category": "shutdown",
            "title": f"Eliminate standby/phantom load on {device_name}",
            "description": (
                f"{device_name} draws a steady ~{night_avg:.2f} kWh/hour baseline overnight even when "
                f"unused. This is characteristic of standby/phantom load. A scheduled shutdown or "
                f"smart-plug cutoff during 00:00-05:00 can eliminate this waste."
            ),
            "estimated_savings_kwh": round(night_avg * 5, 2),
            "estimated_savings_pct": None,
            "priority": "low",
        }]
    return []


def generate_recommendations(
    df: pd.DataFrame,
    device_name: str,
    device_type: str | None = None,
    peak_windows: list[dict] | None = None,
) -> list[dict]:
    """Run every rule and return the combined, deduplicated recommendation list."""
    if df.empty or len(df) < 24:
        return []

    peak_hours = []
    if peak_windows:
        for w in peak_windows:
            start_h = pd.Timestamp(w["start"]).hour
            end_h = pd.Timestamp(w["end"]).hour
            peak_hours.extend(range(start_h, end_h + 1))
    peak_hours = sorted(set(peak_hours))

    recs = []
    recs += rule_load_balancing(df, device_name)
    recs += rule_off_peak_shift(df, device_name, peak_hours)
    recs += rule_scheduling_hvac(df, device_name, device_type, "occupancy" in df.columns)
    recs += rule_shutdown_recommendation(df, device_name)

    priority_rank = {"high": 0, "medium": 1, "low": 2}
    recs.sort(key=lambda r: priority_rank.get(r["priority"], 3))
    return recs
