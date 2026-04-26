import logging
import logging.config
from contextvars import ContextVar

from .config import LOG_DIR


request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
fund_code_var: ContextVar[str] = ContextVar("fund_code", default="-")
task_id_var: ContextVar[str] = ContextVar("task_id", default="-")
stage_var: ContextVar[str] = ContextVar("stage", default="-")


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get("-")
        record.fund_code = fund_code_var.get("-")
        record.task_id = task_id_var.get("-")
        record.stage = stage_var.get("-")
        return True


def setup_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    fmt = (
        "%(asctime)s | %(levelname)s | %(name)s | request_id=%(request_id)s | "
        "fund_code=%(fund_code)s | task_id=%(task_id)s | stage=%(stage)s | %(message)s"
    )
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {"context": {"()": ContextFilter}},
        "formatters": {"standard": {"format": fmt}},
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "standard",
                "filters": ["context"],
                "level": "INFO",
            },
            "app_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": str(LOG_DIR / "app.log"),
                "maxBytes": 5_000_000,
                "backupCount": 5,
                "encoding": "utf-8",
                "formatter": "standard",
                "filters": ["context"],
                "level": "INFO",
            },
            "train_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": str(LOG_DIR / "train.log"),
                "maxBytes": 5_000_000,
                "backupCount": 5,
                "encoding": "utf-8",
                "formatter": "standard",
                "filters": ["context"],
                "level": "INFO",
            },
            "error_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": str(LOG_DIR / "error.log"),
                "maxBytes": 5_000_000,
                "backupCount": 5,
                "encoding": "utf-8",
                "formatter": "standard",
                "filters": ["context"],
                "level": "ERROR",
            },
        },
        "loggers": {
            "": {"handlers": ["console", "app_file", "error_file"], "level": "INFO"},
            "train": {"handlers": ["console", "train_file", "error_file"], "level": "INFO", "propagate": False},
        },
    }
    logging.config.dictConfig(config)


def set_log_context(
    request_id: str | None = None,
    fund_code: str | None = None,
    task_id: str | None = None,
    stage: str | None = None,
) -> None:
    if request_id is not None:
        request_id_var.set(request_id)
    if fund_code is not None:
        fund_code_var.set(fund_code)
    if task_id is not None:
        task_id_var.set(task_id)
    if stage is not None:
        stage_var.set(stage)
