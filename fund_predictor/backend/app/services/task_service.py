import json
import logging
import uuid
from datetime import datetime

from backend.app.core.errors import AppError
from backend.app.core.logging_config import set_log_context
from backend.app.db.database import get_conn
from backend.app.services.feature_service import build_features
from backend.app.services.model_registry_service import save_model_archive
from backend.app.services.model_selection_service import select_and_train

logger = logging.getLogger("train")


def create_task(fund_code: str) -> str:
    task_id = f"train_{fund_code}_{uuid.uuid4().hex[:10]}"
    now = datetime.now().isoformat(timespec="seconds")
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO tasks(task_id, fund_code, status, progress, stage, message, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (task_id, fund_code, "running", 0, "queued", "Training task submitted", now, now),
        )
    return task_id


def update_task(
    task_id: str,
    status: str | None = None,
    progress: int | None = None,
    stage: str | None = None,
    message: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    error_details: dict | None = None,
) -> None:
    fields = []
    vals = []
    for key, val in {
        "status": status,
        "progress": progress,
        "stage": stage,
        "message": message,
        "error_code": error_code,
        "error_message": error_message,
        "error_details": json.dumps(error_details, ensure_ascii=False) if error_details is not None else None,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }.items():
        if val is not None:
            fields.append(f"{key}=?")
            vals.append(val)
    vals.append(task_id)
    with get_conn() as conn:
        conn.execute(f"UPDATE tasks SET {', '.join(fields)} WHERE task_id=?", vals)


def get_task(task_id: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
    if not row:
        return None
    data = dict(row)
    if data.get("error_details"):
        try:
            data["details"] = json.loads(data["error_details"])
        except json.JSONDecodeError:
            data["details"] = {"raw": data["error_details"]}
    return data


def run_training_task(task_id: str, fund_code: str, force: bool = True) -> None:
    set_log_context(task_id=task_id, fund_code=fund_code, stage="training_start")
    try:
        update_task(task_id, progress=10, stage="data_fetch", message="Reading or downloading NAV and index data")
        data_full, data_train, _ = build_features(fund_code, require_fresh=force)
        update_task(task_id, progress=30, stage="feature_build", message="Feature build completed")

        def progress_cb(progress: int, stage: str, message: str) -> None:
            set_log_context(stage=stage)
            update_task(task_id, progress=progress, stage=stage, message=message)

        bundle, metrics, backtest, direction_backtest = select_and_train(data_train, progress_cb=progress_cb)
        update_task(task_id, progress=88, stage="model_save", message="Saving model archive")
        config = {
            "last_train_date": str(data_train["date"].max().date()),
            "data_start_date": str(data_full["date"].min().date()),
            "data_end_date": str(data_full["date"].max().date()),
            "train_window": 180,
        }
        save_model_archive(fund_code, bundle, config, metrics, backtest, direction_backtest)
        set_log_context(stage="model_saved")
        logger.info("model_saved fund_code=%s point_model=%s direction_model=%s", fund_code, bundle.point_model_name, bundle.direction_model_name)
        update_task(task_id, status="success", progress=100, stage="completed", message="Training completed")
    except AppError as exc:
        set_log_context(stage=exc.stage)
        logger.exception("training_failed app_error code=%s", exc.code)
        update_task(
            task_id,
            status="failed",
            progress=100,
            stage=exc.stage,
            message=exc.message,
            error_code=exc.code,
            error_message=exc.message,
            error_details=exc.details,
        )
    except Exception as exc:
        set_log_context(stage="training_failed")
        logger.exception("training_failed unexpected")
        update_task(
            task_id,
            status="failed",
            progress=100,
            stage="training_failed",
            message=str(exc),
            error_code="TRAINING_FAILED",
            error_message=str(exc),
            error_details={"reason": str(exc)},
        )
