from datetime import datetime, timedelta
from sqlalchemy import select
from app.core.database import async_session
from app.models.fund_profile import FundProfileCache
from app.models.prediction import Prediction
from app.models.data_status import DataStatus
from app.models.fund_nav import FundNav
from app.core.scheduler import scheduler
from app.services.model.versioning import list_versions, MODEL_DIR
from pathlib import Path


async def daily_nav_update():
    async with async_session() as session:
        result = await session.execute(select(FundProfileCache.fund_code))
        fund_codes = [r[0] for r in result.all()]
    for fund_code in fund_codes:
        try:
            from app.services.data.nav_service import fetch_and_store_nav
            await fetch_and_store_nav(fund_code)
        except Exception:
            pass
    try:
        from app.services.data.index_service import fetch_all_indices
        await fetch_all_indices()
    except Exception:
        pass
    async with async_session() as session:
        existing = await session.execute(
            select(DataStatus).where(DataStatus.data_type == "nav_update", DataStatus.identifier == "all")
        )
        record = existing.scalar_one_or_none()
        if record:
            record.latest_date = datetime.now().strftime("%Y-%m-%d")
            record.last_updated = datetime.now()
            record.status = "ok"
        else:
            session.add(DataStatus(data_type="nav_update", identifier="all", latest_date=datetime.now().strftime("%Y-%m-%d"), status="ok", last_updated=datetime.now()))
        await session.flush()


async def backfill_prediction_errors():
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    async with async_session() as session:
        result = await session.execute(
            select(Prediction).where(Prediction.target_date == yesterday, Prediction.actual_return.is_(None))
        )
        predictions = result.scalars().all()
    for pred in predictions:
        try:
            async with async_session() as session:
                nav_result = await session.execute(
                    select(FundNav).where(FundNav.fund_code == pred.fund_code, FundNav.nav_date == yesterday)
                )
                nav_row = nav_result.scalar_one_or_none()
                if nav_row is not None and nav_row.daily_return is not None:
                    p = await session.get(Prediction, pred.id)
                    if p:
                        p.actual_return = float(nav_row.daily_return)
                        p.error = abs(float(nav_row.daily_return) - p.predicted_return)
                        p.direction_correct = 1 if (float(nav_row.daily_return) > 0) == (p.predicted_return > 0) else 0
                        p.interval_covered = 1 if p.lower_bound <= float(nav_row.daily_return) <= p.upper_bound else 0
                        await session.flush()
        except Exception:
            continue


async def weekly_model_health_check():
    async with async_session() as session:
        result = await session.execute(select(FundProfileCache.fund_code))
        fund_codes = [r[0] for r in result.all()]
    stale_funds = []
    for fund_code in fund_codes:
        try:
            versions = list_versions(fund_code)
            if not versions:
                stale_funds.append(fund_code)
                continue
            active = [v for v in versions if v.get("is_active")]
            if not active:
                stale_funds.append(fund_code)
                continue
            saved_at = active[0].get("saved_at", "")
            if saved_at:
                saved_date = datetime.fromisoformat(saved_at)
                if (datetime.now() - saved_date).days > 30:
                    stale_funds.append(fund_code)
        except Exception:
            continue
    async with async_session() as session:
        record = DataStatus(data_type="model_health", identifier="check", latest_date=datetime.now().strftime("%Y-%m-%d"), status="ok", row_count=len(stale_funds), last_updated=datetime.now())
        session.add(record)
        await session.flush()
    return stale_funds


def register_scheduled_jobs(scheduler):
    scheduler.add_job(daily_nav_update, "cron", hour=17, minute=30, day_of_week="mon-fri", id="daily_nav_update", replace_existing=True)
    scheduler.add_job(backfill_prediction_errors, "cron", hour=21, minute=30, day_of_week="mon-fri", id="backfill_errors", replace_existing=True)
    scheduler.add_job(weekly_model_health_check, "cron", day_of_week="sat", hour=8, minute=0, id="model_health_check", replace_existing=True)