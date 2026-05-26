from fastapi import APIRouter, Depends

from app.core.database import get_db
from app.schemas.common import ApiResponse
from sqlalchemy import select, func
from app.models.prediction import Prediction
from app.models.train_task import TrainTask
from app.models.fund_nav import FundNav
from app.models.fund_profile import FundProfileCache
from app.models.data_status import DataStatus

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats")
async def dashboard_stats(db=Depends(get_db)):
    total_models = 0
    total_predictions = 0
    avg_direction_acc = None
    today_preds = 0
    data_freshness = "unknown"

    try:
        result = await db.execute(select(func.count(TrainTask.id)).where(TrainTask.status == "success"))
        total_models = result.scalar() or 0

        result2 = await db.execute(select(func.count(Prediction.id)))
        total_predictions = result2.scalar() or 0

        if total_predictions > 0:
            result3 = await db.execute(
                select(func.avg(Prediction.direction_correct)).where(Prediction.direction_correct.isnot(None))
            )
            val = result3.scalar()
            avg_direction_acc = round(float(val), 4) if val else None

        from datetime import datetime, timedelta
        today_str = datetime.now().strftime("%Y-%m-%d")
        result4 = await db.execute(
            select(func.count(Prediction.id)).where(Prediction.predict_date == today_str)
        )
        today_preds = result4.scalar() or 0

        nav_result = await db.execute(
            select(FundNav.nav_date).order_by(FundNav.nav_date.desc()).limit(1)
        )
        latest_nav_row = nav_result.scalar_one_or_none()
        if latest_nav_row:
            try:
                latest_date = str(latest_nav_row.nav_date)
                days_ago = (datetime.now() - datetime.strptime(latest_date, "%Y-%m-%d")).days
                if days_ago <= 1:
                    data_freshness = "fresh"
                elif days_ago <= 7:
                    data_freshness = "stale"
                else:
                    data_freshness = "very_stale"
            except Exception:
                pass
    except Exception:
        pass

    return ApiResponse(ok=True, data={
        "total_models": total_models,
        "total_predictions": total_predictions,
        "avg_direction_accuracy": avg_direction_acc,
        "today_predictions": today_preds,
        "data_freshness": data_freshness,
    })


@router.get("/recent-predictions")
async def recent_predictions(limit: int = 10, db=Depends(get_db)):
    result = await db.execute(
        select(Prediction).order_by(Prediction.created_at.desc()).limit(limit)
    )
    rows = result.scalars().all()
    predictions = []
    for r in rows:
        predictions.append({
            "fund_code": r.fund_code,
            "predict_date": r.predict_date,
            "target_date": r.target_date,
            "predicted_return": r.predicted_return,
            "direction": r.direction,
            "direction_prob": r.direction_prob,
            "actual_return": r.actual_return,
            "direction_correct": r.direction_correct,
            "model_type": r.model_type,
        })
    return ApiResponse(ok=True, data={"predictions": predictions, "total": len(predictions)})