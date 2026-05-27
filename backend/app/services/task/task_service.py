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

    def _sync_train(nav_data_list: list, fund_type_str: str, use_simplified: bool = False) -> dict:
        import time as _time
        from app.services.features.feature_service import build_and_screen
        from app.services.model.trainer import _do_sync_training

        t_start = _time.time()
        features, selected_features = build_and_screen(fund_code, nav_data_list, fund_type_str)
        t_feat = _time.time() - t_start
        metrics = _do_sync_training(nav_data_list, fund_type_str, features, selected_features, fund_code, use_simplified_mode=use_simplified)
        t_total = _time.time() - t_start
        metrics["timing_feature_build"] = round(t_feat, 3)
        metrics["timing_total_train"] = round(t_total, 3)
        return metrics

    try:
        await update_task_status("running", 5, "开始获取净值数据...")

        async with async_session() as s:
            from app.models.fund_nav import FundNav
            from app.services.data.nav_service import fetch_and_store_nav
            
            result = await s.execute(select(func.count(FundNav.id)).where(FundNav.fund_code == fund_code))
            nav_count = result.scalar() or 0
            
            if nav_count < 150:
                await update_task_status("running", 10, f"正在从蛋卷基金拉取净值数据 (当前{nav_count}行)...")
                try:
                    await fetch_and_store_nav(fund_code, s)
                    await update_task_status("running", 15, f"净值数据获取完成，重新查询...")
                except Exception as fetch_err:
                    import traceback
                    error_detail = f"{str(fetch_err)[:80]}\n{traceback.format_exc()[:200]}"
                    await update_task_status("running", 15, f"数据获取尝试失败: {error_detail}")
            
            # 在同一个 session 中重新查询数据（确保能获取到刚提交的数据）
            result = await s.execute(
                select(FundNav).where(FundNav.fund_code == fund_code).order_by(FundNav.nav_date)
            )
            nav_rows = result.scalars().all()

            # 检查是否获取到数据，如果没有则尝试再次获取
            if not nav_rows:
                await update_task_status("running", 15, f"数据库中无数据，尝试强制获取...")
                try:
                    await fetch_and_store_nav(fund_code, s)
                    # 再次查询
                    result = await s.execute(
                        select(FundNav).where(FundNav.fund_code == fund_code).order_by(FundNav.nav_date)
                    )
                    nav_rows = result.scalars().all()
                except Exception as e:
                    await update_task_status("running", 15, f"强制获取失败: {str(e)[:100]}")
            
            # 最终检查
            if not nav_rows:
                raise ValueError(f"基金 {fund_code} 净值数据为空，无法训练。请检查基金代码是否正确或稍后重试。")

            from app.models.fund_profile import FundProfileCache
            profile_result = await s.execute(
                select(FundProfileCache).where(FundProfileCache.fund_code == fund_code)
            )
            profile = profile_result.scalar_one_or_none()
            fund_type = profile.fund_type if profile else "hybrid_equity"

            nav_data_list = [{"nav_date": r.nav_date, "nav": r.nav, "acc_nav": r.acc_nav, "daily_return": r.daily_return} for r in nav_rows]
            
            # 根据原始数据量决定是否使用简化模式
            # 简化模式：原始数据在150-300行之间时使用
            use_simplified = len(nav_data_list) < 300
            if use_simplified:
                await update_task_status("running", 25, f"数据量{len(nav_data_list)}行，将使用简化训练模式...")

        await update_task_status("running", 30, f"数据加载完成，共{len(nav_data_list)}条记录，开始训练模型...")

        metrics = await loop.run_in_executor(executor, _sync_train, nav_data_list, fund_type, use_simplified)
        
        # 根据模式显示不同的完成信息
        if metrics.get("simplified_mode"):
            await update_task_status("success", 100, f"训练完成（简化模式）。注意：该基金历史数据较短，模型预测能力可能受限。")
        else:
            await update_task_status("success", 100, "训练完成")
        async with async_session() as s:
            t = await s.get(TrainTask, task_id)
            if t:
                t.metrics_json = json.dumps(metrics, ensure_ascii=False)
                t.model_version = metrics.get("model_version", "")
                await s.commit()

    except Exception as e:
        error_msg = str(e)[:500]
        # 针对数据不足的情况给出更友好的提示
        if "清洗后数据仅" in error_msg and "行，无法训练" in error_msg:
            error_msg = f"{error_msg}。该基金历史数据较短或存在数据缺失，建议：1) 选择成立时间更长的基金；2) 检查数据源是否完整；3) 稍后再试。"
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
    # 将log_text转换为logs数组，兼容前端显示
    logs = []
    if task.log_text:
        logs = task.log_text.split('\n') if '\n' in task.log_text else [task.log_text]
    
    return {"task_id": task.id, "fund_code": task.fund_code, "status": task.status, "progress": task.progress, "message": task.error_message or "", "log_text": task.log_text or "", "logs": logs, "metrics": json.loads(task.metrics_json) if task.metrics_json else None, "model_version": task.model_version, "created_at": task.created_at.isoformat() if task.created_at else None, "started_at": task.started_at.isoformat() if task.started_at else None, "finished_at": task.finished_at.isoformat() if task.finished_at else None}


async def list_tasks(session, fund_code: str = None, limit: int = 20, offset: int = 0) -> list:
    from app.models.fund_profile import FundProfileCache
    
    query = select(TrainTask).order_by(TrainTask.created_at.desc())
    if fund_code:
        query = query.where(TrainTask.fund_code == fund_code)
    query = query.offset(offset).limit(limit)
    result = await session.execute(query)
    tasks = result.scalars().all()
    
    # 获取所有涉及的基金代码
    fund_codes = [t.fund_code for t in tasks]
    
    # 批量查询基金名称
    fund_names = {}
    if fund_codes:
        profile_result = await session.execute(
            select(FundProfileCache.fund_code, FundProfileCache.fund_name)
            .where(FundProfileCache.fund_code.in_(fund_codes))
        )
        fund_names = {row[0]: row[1] for row in profile_result.all()}
    
    task_list = []
    for t in tasks:
        # 解析 metrics_json 获取评测指标
        metrics = json.loads(t.metrics_json) if t.metrics_json else {}
        
        # 构建评测指标摘要
        metrics_summary = {}
        if metrics:
            # MAE (Mean Absolute Error)
            if "valid_mae" in metrics:
                metrics_summary["mae"] = round(metrics["valid_mae"], 4)
            # MSE (Mean Squared Error) - 如果有的话
            if "valid_mse" in metrics:
                metrics_summary["mse"] = round(metrics["valid_mse"], 4)
            # RMSE (Root Mean Squared Error) - 如果有的话
            if "valid_rmse" in metrics:
                metrics_summary["rmse"] = round(metrics["valid_rmse"], 4)
            # 方向准确率
            if "valid_direction_accuracy" in metrics:
                metrics_summary["direction_accuracy"] = round(metrics["valid_direction_accuracy"], 4)
            # 训练数据行数
            if "train_rows" in metrics:
                metrics_summary["train_rows"] = metrics["train_rows"]
            # 是否简化模式
            if "simplified_mode" in metrics:
                metrics_summary["simplified_mode"] = metrics["simplified_mode"]
        
        task_list.append({
            "task_id": t.id,
            "fund_code": t.fund_code,
            "fund_name": fund_names.get(t.fund_code, ""),
            "status": t.status,
            "progress": t.progress,
            "model_version": t.model_version,
            "metrics_summary": metrics_summary,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "finished_at": t.finished_at.isoformat() if t.finished_at else None
        })
    
    return task_list