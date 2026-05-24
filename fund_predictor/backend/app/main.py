import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import backtest, dashboard, fund, intraday, model, task, train
from app.core.config import STATIC_DIR, ensure_dirs
from app.core.errors import AppError
from app.core.logging_config import (
    api_logger,
    request_id_var,
    set_log_context,
    setup_logging,
)
from app.db.database import init_db

ensure_dirs()
setup_logging()
init_db()

logger = logging.getLogger(__name__)
app = FastAPI(
    title="基金 T+1 净值涨跌幅区间预测系统",
    version="2.4.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    start_time = time.perf_counter()
    request_id = uuid.uuid4().hex[:12]
    set_log_context(request_id=request_id, fund_code="-", task_id="-", stage="request_in")

    logger.info(
        "request_start method=%s path=%s client=%s",
        request.method,
        request.url.path,
        request.client.host if request.client else "-",
    )

    try:
        response = await call_next(request)
    except Exception as e:
        elapsed = time.perf_counter() - start_time
        logger.error(
            "request_failed method=%s path=%s status=ERROR elapsed_ms=%.1f",
            request.method,
            request.url.path,
            elapsed * 1000,
        )
        _log_api_request(request, None, elapsed, str(e))
        raise

    elapsed = time.perf_counter() - start_time
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time-ms"] = f"{elapsed * 1000:.1f}"

    _log_api_request(request, response.status_code, elapsed)

    set_log_context(stage="request_done")
    return response


def _log_api_request(request: Request, status_code: int | None, elapsed: float,
                     error_msg: str | None = None) -> None:
    record = logging.LogRecord(
        name="api.access",
        level=logging.INFO if status_code and status_code < 400 else logging.ERROR,
        pathname=__file__,
        lineno=0,
        msg="api_request",
        args=(),
        exc_info=None,
    )
    record.extra_data = {
        "method": request.method,
        "path": request.url.path,
        "query": str(request.query_params),
        "status_code": status_code or 500,
        "elapsed_ms": round(elapsed * 1000, 2),
        "client_ip": request.client.host if request.client else "-",
        "error": error_msg,
    }
    api_logger.handle(record)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    logger.exception("app_error code=%s", exc.code)
    status = getattr(exc, 'http_status', 400)
    return JSONResponse(status_code=status, content={"ok": False, "error": exc.to_dict(request_id=request_id_var.get())})


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
app.include_router(fund.admin_router)
app.include_router(intraday.router)
app.include_router(train.router)
app.include_router(task.router)
app.include_router(model.router)
app.include_router(backtest.router)
app.include_router(dashboard.router)

app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")