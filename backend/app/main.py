from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.db.database import init_db
from app.routers import dataset, forecast, anomaly, optimization, simulation, analytics
from app.tasks.background import start_scheduler, shutdown_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()
    yield
    shutdown_scheduler()


app = FastAPI(
    title=settings.app_name,
    description=(
        "AI-powered platform for energy consumption forecasting, peak-usage prediction, "
        "anomaly detection, optimization recommendations, and what-if scenario simulation."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dataset.router, prefix=settings.api_v1_prefix)
app.include_router(forecast.router, prefix=settings.api_v1_prefix)
app.include_router(anomaly.router, prefix=settings.api_v1_prefix)
app.include_router(optimization.router, prefix=settings.api_v1_prefix)
app.include_router(simulation.router, prefix=settings.api_v1_prefix)
app.include_router(analytics.router, prefix=settings.api_v1_prefix)


@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "service": settings.app_name}


@app.get("/health", tags=["Health"])
def health():
    return {"status": "healthy"}
