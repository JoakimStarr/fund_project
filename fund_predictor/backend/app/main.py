import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.app.api import backtest, fund, model, task, train
from backend.app.core.config import STATIC_DIR, ensure_dirs
from backend.app.core.errors import AppError
from backend.app.core.logging_config import request_id_var, set_log_context, setup_logging
from backend.app.db.database import init_db

ensure_dirs()
setup_logging()
init_db()

logger = logging.getLogger(__name__)
app = FastAPI(title="基金 T+1 净值涨跌幅区间预测系统")


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = uuid.uuid4().hex[:12]
    set_log_context(request_id=request_id, fund_code="-", task_id="-", stage="request")
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    except Exception:
        logger.exception("unhandled_request_error")
        raise


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    logger.exception("app_error code=%s", exc.code)
    return JSONResponse(status_code=400, content={"ok": False, "error": exc.to_dict(request_id=request_id_var.get())})


@app.exception_handler(Exception)
async def exception_handler(request: Request, exc: Exception):
    logger.exception("unexpected_error")
    return JSONResponse(
        status_code=500,
        content={
            "ok": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": str(exc),
                "stage": "unknown",
                "request_id": request_id_var.get(),
                "task_id": None,
                "details": {},
            },
        },
    )


app.include_router(fund.router)
app.include_router(train.router)
app.include_router(task.router)
app.include_router(model.router)
app.include_router(backtest.router)

app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
