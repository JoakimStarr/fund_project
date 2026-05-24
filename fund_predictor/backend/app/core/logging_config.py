import json
import logging
import logging.config
import logging.handlers
import threading
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path

from .config import ROOT_DIR

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
fund_code_var: ContextVar[str] = ContextVar("fund_code", default="-")
task_id_var: ContextVar[str] = ContextVar("task_id", default="-")
stage_var: ContextVar[str] = ContextVar("stage", default="-")


def _load_yaml_config() -> dict:
    cfg_path = ROOT_DIR / "config.yaml"
    if cfg_path.exists():
        import yaml
        with open(cfg_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get("-")
        record.fund_code = fund_code_var.get("-")
        record.task_id = task_id_var.get("-")
        record.stage = stage_var.get("-")
        return True


class StructuredJSONHandler(logging.Handler):
    """每条日志输出为一行JSON，适合ELK/Fluentd采集"""

    def __init__(self, filename: str, max_bytes: int = 10_485_760,
                 maxBytes: int = 0,
                 backup_count: int = 30, backupCount: int = 0,
                 encoding: str = "utf-8"):
        super().__init__()
        self._handler = logging.handlers.RotatingFileHandler(
            filename,
            maxBytes=maxBytes or max_bytes,
            backupCount=backupCount or backup_count,
            encoding=encoding,
        )

    def emit(self, record: logging.LogRecord) -> None:
        try:
            log_entry = {
                "@timestamp": datetime.now(timezone.utc).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno,
                "thread": threading.current_thread().name,
                "request_id": getattr(record, "request_id", "-"),
                "fund_code": getattr(record, "fund_code", "-"),
                "task_id": getattr(record, "task_id", "-"),
                "stage": getattr(record, "stage", "-"),
                "extra": getattr(record, "extra_data", {}),
                "exception": self.format(record) if record.exc_info else None,
            }
            json_line = json.dumps(log_entry, ensure_ascii=False, default=str)
            new_record = logging.LogRecord(
                name=record.name,
                level=record.levelno,
                pathname=__file__,
                lineno=0,
                msg=json_line,
                args=(),
                exc_info=None,
            )
            self._handler.emit(new_record)
        except Exception:
            self.handleError(record)

    def close(self) -> None:
        self._handler.close()
        super().close()


_DETAILED_FMT = (
    "%(asctime)s | %(levelname)-5s | %(name)s | "
    "request_id=%(request_id)s | fund_code=%(fund_code)s | "
    "task_id=%(task_id)s | stage=%(stage)s | %(message)s"
)

_CONSOLE_FMT = (
    "%(asctime)s | %(levelname)-5s | %(name)-20s | %(message)s"
)


def setup_logging() -> None:
    cfg = _load_yaml_config()
    log_cfg = cfg.get("logging", {})

    log_dir = Path(ROOT_DIR) / log_cfg.get("dir", "logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    file_cfg = log_cfg.get("file", {})
    max_bytes = int(file_cfg.get("max_bytes", 10_485_760))
    backup_count = int(file_cfg.get("backup_count", 30))
    encoding = file_cfg.get("encoding", "utf-8")

    console_cfg = log_cfg.get("console", {})
    console_level = console_cfg.get("level", "INFO")

    handlers_cfg = log_cfg.get("handlers", {})
    handler_defs = {}
    logger_handlers = ["console"]
    train_logger_handlers = []

    _json_handler_specs = {}

    app_handler = handlers_cfg.get("app", {})
    if app_handler.get("filename"):
        handler_defs["app_file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(log_dir / app_handler["filename"]),
            "maxBytes": max_bytes,
            "backupCount": backup_count,
            "encoding": encoding,
            "formatter": "detailed",
            "filters": ["context"],
            "level": app_handler.get("level", "INFO"),
        }
        logger_handlers.append("app_file")

    api_handler = handlers_cfg.get("api", {})
    if api_handler.get("filename") and api_handler.get("format") == "json":
        _json_handler_specs["api_json"] = {
            "filename": str(log_dir / api_handler["filename"]),
            "level": api_handler.get("level", "INFO"),
        }
        logger_handlers.append("api_json")

    train_handler = handlers_cfg.get("train", {})
    if train_handler.get("filename"):
        handler_defs["train_file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(log_dir / train_handler["filename"]),
            "maxBytes": max_bytes,
            "backupCount": backup_count,
            "encoding": encoding,
            "formatter": "detailed",
            "filters": ["context"],
            "level": train_handler.get("level", "DEBUG"),
        }
        train_logger_handlers.extend(["console", "train_file"])

    error_handler = handlers_cfg.get("error", {})
    if error_handler.get("filename"):
        handler_defs["error_file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(log_dir / error_handler["filename"]),
            "maxBytes": max_bytes,
            "backupCount": backup_count,
            "encoding": encoding,
            "formatter": "detailed",
            "filters": ["context"],
            "level": error_handler.get("level", "ERROR"),
        }
        logger_handlers.append("error_file")
        train_logger_handlers.append("error_file")

    audit_handler = handlers_cfg.get("audit", {})
    if audit_handler.get("filename") and audit_handler.get("format") == "json":
        _json_handler_specs["audit_json"] = {
            "filename": str(log_dir / audit_handler["filename"]),
            "level": audit_handler.get("level", "INFO"),
        }

    perf_handler = handlers_cfg.get("perf", {})
    if perf_handler.get("filename") and perf_handler.get("format") == "json":
        _json_handler_specs["perf_json"] = {
            "filename": str(log_dir / perf_handler["filename"]),
            "level": perf_handler.get("level", "INFO"),
        }

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {"context": {"()": ContextFilter}},
        "formatters": {
            "detailed": {"format": _DETAILED_FMT},
            "console": {"format": _CONSOLE_FMT},
        },
        "handlers": {
            **{
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "console",
                    "filters": ["context"],
                    "level": console_level,
                }
            },
            **handler_defs,
        },
        "loggers": {
            "": {
                "handlers": [h for h in logger_handlers if h not in _json_handler_specs],
                "level": log_cfg.get("level", "INFO"),
            },
            "train": {
                "handlers": train_logger_handlers or ["console"],
                "level": "DEBUG",
                "propagate": False,
            },
        },
    }

    logging.config.dictConfig(config)
    _setup_third_party_loggers(cfg)

    for name, spec in _json_handler_specs.items():
        jh = StructuredJSONHandler(
            filename=spec["filename"],
            max_bytes=max_bytes,
            backup_count=backup_count,
            encoding=encoding,
        )
        jh.setLevel(logging.getLevelName(spec.get("level", "INFO")))

        if name == "api_json":
            api_logger.addHandler(jh)
            logging.getLogger("").addHandler(jh)
        elif name == "audit_json":
            audit_logger.addHandler(jh)
        elif name == "perf_json":
            perf_logger.addHandler(jh)

    root = logging.getLogger()
    all_handler_names = list(config["handlers"].keys()) + list(_json_handler_specs.keys())
    root.info("logging_system_initialized log_dir=%s handlers=%s", str(log_dir), all_handler_names)


def _setup_third_party_loggers(global_cfg: dict) -> None:
    third_party = global_cfg.get("logging", {}).get("third_party", {})
    for lib_name, level in third_party.items():
        logging.getLogger(lib_name).setLevel(logging.getLevelName(level))


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


def get_log_context() -> dict:
    return {
        "request_id": request_id_var.get("-"),
        "fund_code": fund_code_var.get("-"),
        "task_id": task_id_var.get("-"),
        "stage": stage_var.get("-"),
    }


api_logger = logging.getLogger("api.access")
audit_logger = logging.getLogger("audit")
perf_logger = logging.getLogger("performance")


def audit_log(action: str, target: str, details: dict | None = None,
              user_id: str | None = None) -> None:
    record = logging.LogRecord(
        name="audit",
        level=logging.INFO,
        pathname=__file__,
        lineno=0,
        msg=f"audit_action={action} target={target}",
        args=(),
        exc_info=None,
    )
    record.extra_data = {
        "action": action,
        "target": target,
        "details": details or {},
        "user_id": user_id or "-",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    audit_logger.handle(record)
