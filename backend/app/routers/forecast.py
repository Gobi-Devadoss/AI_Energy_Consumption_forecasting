from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime
from app.db.database import get_db, SessionLocal
from app.db import models
from app.schemas.forecast import ForecastRequest, ForecastResponse, ModelComparisonResponse
from app.services import forecasting_service

router = APIRouter(prefix="/forecast", tags=["Forecasting"])


def _persist_forecast(db: Session, req: ForecastRequest, result: dict) -> models.ForecastRun:
    points_df = forecasting_service.flag_peaks(result["points"])
    run = models.ForecastRun(
        device_id=req.device_id,
        building_id=req.building_id,
        granularity=req.granularity,
        horizon=req.horizon,
        model_used=result["model_used"],
        mae=result["metrics"].get("mae"),
        rmse=result["metrics"].get("rmse"),
        mape=result["metrics"].get("mape"),
        status="completed",
    )
    db.add(run)
    db.flush()

    for _, row in points_df.iterrows():
        db.add(models.ForecastPoint(
            run_id=run.id,
            timestamp=row["timestamp"],
            predicted_kwh=float(row["predicted_kwh"]),
            lower_bound=float(row["lower_bound"]) if row.get("lower_bound") is not None else None,
            upper_bound=float(row["upper_bound"]) if row.get("upper_bound") is not None else None,
            is_peak=bool(row.get("is_peak", False)),
        ))

    windows = forecasting_service.peak_windows(points_df)
    for w in windows:
        db.add(models.Alert(
            device_id=req.device_id,
            building_id=req.building_id,
            alert_type="peak_forecast",
            message=w["message"],
            severity="warning",
            window_start=datetime.fromisoformat(w["start"]),
            window_end=datetime.fromisoformat(w["end"]),
        ))

    db.commit()
    db.refresh(run)
    return run, points_df, windows


def _run_forecast_job(req: ForecastRequest):
    """Executed in a background thread via BackgroundTasks - non-blocking ML execution."""
    db = SessionLocal()
    run = models.ForecastRun(
        device_id=req.device_id, building_id=req.building_id,
        granularity=req.granularity, horizon=req.horizon,
        model_used=req.model, status="running",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    try:
        df = forecasting_service.load_series(db, req.device_id, req.building_id, req.granularity)
        result = forecasting_service.run_forecast(df, req.horizon, req.granularity, req.model)
        db.delete(run)
        db.commit()
        _persist_forecast(db, req, result)
    except Exception as e:  # noqa: BLE001
        run.status = "failed"
        run.error_message = str(e)
        db.commit()
    finally:
        db.close()


@router.post("/generate", response_model=ForecastResponse)
def generate_forecast(req: ForecastRequest, db: Session = Depends(get_db)):
    """
    Synchronous forecast generation - returns the result immediately. Use
    /generate-async for large/expensive jobs (e.g. LSTM on 30d horizon)
    that should run in the background instead of blocking the request.
    """
    if not req.device_id and not req.building_id:
        raise HTTPException(status_code=400, detail="Provide either device_id or building_id")
    try:
        df = forecasting_service.load_series(db, req.device_id, req.building_id, req.granularity)
        result = forecasting_service.run_forecast(df, req.horizon, req.granularity, req.model)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    run, points_df, windows = _persist_forecast(db, req, result)

    return ForecastResponse(
        run_id=run.id,
        device_id=req.device_id,
        building_id=req.building_id,
        granularity=req.granularity,
        horizon=req.horizon,
        model_used=result["model_used"],
        mae=result["metrics"].get("mae"),
        rmse=result["metrics"].get("rmse"),
        mape=result["metrics"].get("mape"),
        points=points_df.to_dict("records"),
        peak_windows=windows,
    )


@router.post("/generate-async", status_code=202)
def generate_forecast_async(req: ForecastRequest, background_tasks: BackgroundTasks):
    """Queue a forecast job to run in the background; poll /forecast/runs/{id} for status."""
    if not req.device_id and not req.building_id:
        raise HTTPException(status_code=400, detail="Provide either device_id or building_id")
    background_tasks.add_task(_run_forecast_job, req)
    return {"status": "queued", "message": "Forecast job queued for background execution"}


@router.get("/runs/{run_id}", response_model=ForecastResponse)
def get_forecast_run(run_id: int, db: Session = Depends(get_db)):
    run = db.query(models.ForecastRun).filter(models.ForecastRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Forecast run not found")
    if run.status != "completed":
        raise HTTPException(status_code=409, detail=f"Forecast run status: {run.status}")
    points = [{
        "timestamp": p.timestamp, "predicted_kwh": p.predicted_kwh,
        "lower_bound": p.lower_bound, "upper_bound": p.upper_bound, "is_peak": p.is_peak,
    } for p in run.points]
    return ForecastResponse(
        run_id=run.id, device_id=run.device_id, building_id=run.building_id,
        granularity=run.granularity, horizon=run.horizon, model_used=run.model_used,
        mae=run.mae, rmse=run.rmse, mape=run.mape, points=points, peak_windows=[],
    )


@router.post("/compare-models", response_model=ModelComparisonResponse)
def compare_models(req: ForecastRequest, db: Session = Depends(get_db)):
    """Run every available model on the same data and compare backtest accuracy - Model Comparison dashboard."""
    if not req.device_id and not req.building_id:
        raise HTTPException(status_code=400, detail="Provide either device_id or building_id")
    df = forecasting_service.load_series(db, req.device_id, req.building_id, req.granularity)
    if df.empty or len(df) < 8:
        raise HTTPException(status_code=400, detail="Not enough historical data to compare models")

    results = []
    for model_name in ["prophet", "lstm", "arima", "regression"]:
        try:
            r = forecasting_service.run_forecast(df, req.horizon, req.granularity, model_name)
            results.append({
                "model": model_name, "status": "success",
                "mae": r["metrics"].get("mae"), "rmse": r["metrics"].get("rmse"), "mape": r["metrics"].get("mape"),
            })
        except Exception as e:  # noqa: BLE001
            results.append({"model": model_name, "status": "failed", "error": str(e)})

    return ModelComparisonResponse(
        device_id=req.device_id, building_id=req.building_id, horizon=req.horizon, results=results,
    )
