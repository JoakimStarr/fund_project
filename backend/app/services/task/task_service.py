import uuid
import json
import asyncio
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import select, func
from app.models.train_task import TrainTask

executor = ThreadPoolExecutor(max_workers=2)


def _get_task_id() -> str:
    return str(uuid.uuid4())[:8]


async def enqueue_train(fund_code: str, session, force_retrain: bool = False) -> dict:
    task_id = _get_task_id()
    task = TrainTask(id=task_id, fund_code=fund_code, status="pending", force_retrain=1 if force_retrain else 0, progress=0, created_at=datetime.now())
    session.add(task)
    await session.commit()
    asyncio.create_task(_execute_train(task_id, fund_code))
    return {"task_id": task_id, "fund_code": fund_code, "status": "pending", "progress": 0}


async def _execute_train(task_id: str, fund_code: str):
    from app.core.database import async_session
    loop = asyncio.get_event_loop()

    async def update_task_status(status: str, progress: int, log_text: str):
        try:
            async with async_session() as s:
                t = await s.get(TrainTask, task_id)
                if t:
                    t.status = status
                    t.progress = progress
                    t.log_text = log_text
                    if status == "running" and not t.started_at:
                        t.started_at = datetime.now()
                    if status in ("success", "failed"):
                        t.finished_at = datetime.now()
                    await s.commit()
        except Exception:
            pass

    def _sync_train(nav_data_list: list, fund_type_str: str) -> dict:
        from app.services.features.feature_service import build_and_screen
        from app.services.model.trainer import _do_sync_training
        features, selected_features = build_and_screen(fund_code, nav_data_list, fund_type_str)
        metrics = _do_sync_training(nav_data_list, fund_type_str, features, selected_features, fund_code)
        return metrics

    try:
        await update_task_status("running", 5, "开始获取净值数据...")

        async with async_session() as s:
            from app.models.fund_nav import FundNav
            result = await s.execute(select(func.count(FundNav.id)).where(FundNav.fund_code == fund_code))
            nav_count = result.scalar() or 0
        if nav_count < 150:
            await update_task_status("running", 10, f"正在从蛋卷基金拉取净值数据 (当前{nav_count}行)...")
            async with async_session() as s:
                from app.services.data.nav_service import fetch_and_store_nav
                await fetch_and_store_nav(fund_code, s)

        async with async_session() as s:
            from app.models.fund_nav import FundNav
            result = await s.execute(
                select(FundNav).where(FundNav.fund_code == fund_code).order_by(FundNav.nav_date)
            )
            nav_rows = result.scalars().all()

            from app.models.fund_profile import FundProfileCache
            profile_result = await s.execute(
                select(FundProfileCache).where(FundProfileCache.fund_code == fund_code)
            )
            profile = profile_result.scalar_one_or_none()
            fund_type = profile.fund_type if profile else "hybrid_equity"

            nav_data_list = [{"nav_date": r.nav_date, "nav": r.nav, "acc_nav": r.acc_nav, "daily_return": r.daily_return} for r in nav_rows]

        await update_task_status("running", 30, "开始训练模型...")

        metrics = await loop.run_in_executor(executor, _sync_train, nav_data_list, fund_type)

        await update_task_status("success", 100, "训练完成")
        async with async_session() as s:
            t = await s.get(TrainTask, task_id)
            if t:
                t.metrics_json = json.dumps(metrics, ensure_ascii=False)
                t.model_version = metrics.get("model_version", "")
                await s.commit()

    except Exception as e:
        error_msg = str(e)[:500]
        await update_task_status("failed", 0, f"训练失败: {error_msg}")
        async with async_session() as s:
            t = await s.get(TrainTask, task_id)
            if t:
                t.error_message = error_msg
                await s.commit()


async def get_task_status(task_id: str, session):
    task = await session.get(TrainTask, task_id)
    if task is None:
        return None
    return {"task_id": task.id, "fund_code": task.fund_code, "status": task.status, "progress": task.progress, "message": task.error_message or "", "log_text": task.log_text or "", "metrics": json.loads(task.metrics_json) if task.metrics_json else None, "model_version": task.model_version, "created_at": task.created_at.isoformat() if task.created_at else None, "started_at": task.started_at.isoformat() if task.started_at else None, "finished_at": task.finished_at.isoformat() if task.finished_at else None}


async def list_tasks(session, fund_code: str = None, limit: int = 20, offset: int = 0) -> list:
    query = select(TrainTask).order_by(TrainTask.created_at.desc())
    if fund_code:
        query = query.where(TrainTask.fund_code == fund_code)
    query = query.offset(offset).limit(limit)
    result = await session.execute(query)
    tasks = result.scalars().all()
    return [{"task_id": t.id, "fund_code": t.fund_code, "status": t.status, "progress": t.progress, "model_version": t.model_version, "created_at": t.created_at.isoformat() if t.created_at else None, "finished_at": t.finished_at.isoformat() if t.finished_at else None} for t in tasks]