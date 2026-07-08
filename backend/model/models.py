from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
)
from sqlalchemy.orm import relationship
from datetime import datetime
from core.database import Base


class Building(Base):
    __tablename__ = "buildings"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), unique=True, nullable=False)
    location = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    devices = relationship("Device", back_populates="building", cascade="all, delete-orphan")


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    building_id = Column(Integer, ForeignKey("buildings.id"), nullable=False)
    external_id = Column(String(120), index=True, nullable=False)  # ID as it appears in dataset
    name = Column(String(150), nullable=True)
    device_type = Column(String(80), nullable=True)  # e.g. HVAC, Lighting, Server, Compressor
    rated_capacity_kw = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    building = relationship("Building", back_populates="devices")
    readings = relationship("EnergyReading", back_populates="device", cascade="all, delete-orphan")


class EnergyReading(Base):
    __tablename__ = "energy_readings"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    energy_kwh = Column(Float, nullable=False)
    temperature_c = Column(Float, nullable=True)
    occupancy = Column(Float, nullable=True)  # optional occupancy proxy (0-1) or headcount
    is_interpolated = Column(Boolean, default=False)  # true if we filled a missing timestamp
    source_batch = Column(String(80), nullable=True)  # upload batch id, for traceability

    device = relationship("Device", back_populates="readings")


class ForecastRun(Base):
    __tablename__ = "forecast_runs"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=True)  # null = building/portfolio level
    building_id = Column(Integer, ForeignKey("buildings.id"), nullable=True)
    granularity = Column(String(20), nullable=False)  # hourly / daily
    horizon = Column(String(20), nullable=False)  # 24h / 7d / 30d
    model_used = Column(String(40), nullable=False)  # prophet / lstm / arima / regression
    mae = Column(Float, nullable=True)
    rmse = Column(Float, nullable=True)
    mape = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(20), default="completed")  # queued / running / completed / failed
    error_message = Column(Text, nullable=True)

    points = relationship("ForecastPoint", back_populates="run", cascade="all, delete-orphan")


class ForecastPoint(Base):
    __tablename__ = "forecast_points"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("forecast_runs.id"), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False)
    predicted_kwh = Column(Float, nullable=False)
    lower_bound = Column(Float, nullable=True)
    upper_bound = Column(Float, nullable=True)
    is_peak = Column(Boolean, default=False)

    run = relationship("ForecastRun", back_populates="points")


class AnomalyRecord(Base):
    __tablename__ = "anomaly_records"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False)
    energy_kwh = Column(Float, nullable=False)
    method = Column(String(30), nullable=False)  # isolation_forest / zscore / threshold
    severity = Column(String(20), nullable=False)  # low / medium / high
    score = Column(Float, nullable=True)
    reason = Column(String(255), nullable=True)
    detected_at = Column(DateTime, default=datetime.utcnow)


class Recommendation(Base):
    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=True)
    building_id = Column(Integer, ForeignKey("buildings.id"), nullable=True)
    category = Column(String(40), nullable=False)  # load_balancing / scheduling / shutdown / off_peak
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    estimated_savings_kwh = Column(Float, nullable=True)
    estimated_savings_pct = Column(Float, nullable=True)
    priority = Column(String(20), default="medium")  # low / medium / high
    created_at = Column(DateTime, default=datetime.utcnow)


class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=True)
    building_id = Column(Integer, ForeignKey("buildings.id"), nullable=True)
    scenario_type = Column(String(40), nullable=False)  # occupancy / temperature / shutdown / peak_reduction
    parameters_json = Column(Text, nullable=False)
    baseline_kwh = Column(Float, nullable=False)
    projected_kwh = Column(Float, nullable=False)
    savings_kwh = Column(Float, nullable=False)
    savings_pct = Column(Float, nullable=False)
    cost_impact = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=True)
    building_id = Column(Integer, ForeignKey("buildings.id"), nullable=True)
    alert_type = Column(String(40), nullable=False)  # peak_forecast / threshold_breach / anomaly
    message = Column(String(300), nullable=False)
    severity = Column(String(20), default="info")  # info / warning / critical
    window_start = Column(DateTime, nullable=True)
    window_end = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    acknowledged = Column(Boolean, default=False)
