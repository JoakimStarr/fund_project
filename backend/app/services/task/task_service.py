import uuid
import json
import asyncio
from datetime import datetime
from sqlalchemy import select, func
from app.models.train_task import TrainTask
from app.services.model.trainer import train_model
from app.core.config import settings


def _get_task_id() -> str:
    return str(uuid.uuid4())[:8]


async def enqueue_train(fund_code: str, session, force_retrain: bool = False) -> dict:
    task_id = _get_task_id()
    task = TrainTask(id=task_id, fund_code=fund_code, status="pending", force_retrain=1 if force_retrain else 0, progress=0, created_at=datetime.now())
    session.add(task)
    await session.flush()
    asyncio.create_task(_execute_train(task_id, fund_code))
    return {"task_id": task_id, "fund_code": fund_code, "status": "pending", "progress": 0}


async def _execute_train(task_id: str, fund_code: str):
    from app.core.database import async_session
    try:
        async with async_session() as session:
            task = await session.get(TrainTask, task_id)
            if task:
                task.status = "running"
                task.started_at = datetime.now()
                task.progress = 10
                await session.commit()
        async with async_session() as session:
            task = await session.get(TrainTask, task_id)
            if task:
                task.progress = 30
                await session.commit()
            metrics = await train_model(fund_code, session)
            if task:
                task.status = "success"
                task.progress = 100
                task.metrics_json = json.dumps(metrics, ensure_ascii=False)
                task.model_version = metrics.get("model_version", "")
                task.finished_at = datetime.now()
                await session.commit()
    except Exception as e:
        async with async_session() as session:
            task = await session.get(TrainTask, task_id)
            if task:
                task.status = "failed"
                task.progress = 0
                task.error_message = str(e)
                task.finished_at = datetime.now()
                await session.commit()


async def get_task_status(task_id: str, session):
    task = await session.get(TrainTask, task_id)
    if task is None:
        return None
    return {"task_id": task.id, "fund_code": task.fund_code, "status": task.status, "progress": task.progress, "message": task.error_message or "", "metrics": json.loads(task.metrics_json) if task.metrics_json else None, "model_version": task.model_version, "created_at": task.created_at.isoformat() if task.created_at else None, "started_at": task.started_at.isoformat() if task.started_at else None, "finished_at": task.finished_at.isoformat() if task.finished_at else None}


async def list_tasks(session, fund_code: str = None, limit: int = 20, offset: int = 0) -> list:
    query = select(TrainTask).order_by(TrainTask.created_at.desc())
    if fund_code:
        query = query.where(TrainTask.fund_code == fund_code)
    query = query.offset(offset).limit(limit)
    result = await session.execute(query)
    tasks = result.scalars().all()
    return [{"task_id": t.id, "fund_code": t.fund_code, "status": t.status, "progress": t.progress, "model_version": t.model_version, "created_at": t.created_at.isoformat() if t.created_at else None, "finished_at": t.finished_at.isoformat() if t.finished_at else None} for t in tasks]