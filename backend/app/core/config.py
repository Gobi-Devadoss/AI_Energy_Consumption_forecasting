"""
Central application configuration.
All environment-driven settings live here so the rest of the codebase
never reads os.environ directly.
"""
from pydantic_settings import BaseSettings
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    app_name: str = "AI Energy Consumption Forecasting & Optimization System"
    api_v1_prefix: str = "/api/v1"

    database_url: str = f"sqlite:///{BASE_DIR / 'data' / 'energy.db'}"

    # Where trained model artifacts (Prophet pickles, LSTM weights, scalers) are stored
    model_store_dir: Path = BASE_DIR / "models_store"

    # Where uploaded raw datasets are cached
    upload_dir: Path = BASE_DIR / "data" / "uploads"

    # Forecast horizons (hours) exposed by the API
    horizon_24h_hours: int = 24
    horizon_7d_hours: int = 24 * 7
    horizon_30d_hours: int = 24 * 30

    # Anomaly detection sensitivity defaults
    isolation_forest_contamination: float = 0.03
    zscore_threshold: float = 3.0

    # Simulation defaults
    default_electricity_rate_per_kwh: float = 8.0  # INR/kWh, adjustable per request

    cors_origins: list[str] = ["*"]

    class Config:
        env_file = ".env"


settings = Settings()

settings.model_store_dir.mkdir(parents=True, exist_ok=True)
settings.upload_dir.mkdir(parents=True, exist_ok=True)
(BASE_DIR / "data").mkdir(parents=True, exist_ok=True)
