import functools
import logging
import resource
import time

from .logging_config import perf_logger


def log_performance(operation_name: str):
    """装饰器：记录函数执行时间和资源消耗"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                success = True
            except Exception:
                success = False
                raise
            finally:
                elapsed = time.perf_counter() - start
                _record_perf(operation_name, elapsed, success=success)
            return result
        return wrapper
    return decorator


def record_performance(operation_name: str, elapsed_ms: float,
                       success: bool = True, extra: dict | None = None) -> None:
    """函数式调用：手动记录性能指标"""
    record = logging.LogRecord(
        name="performance",
        level=logging.INFO,
        pathname=__file__,
        lineno=0,
        msg=f"perf operation={operation_name}",
        args=(),
        exc_info=None,
    )
    record.extra_data = {
        "operation": operation_name,
        "elapsed_ms": round(elapsed_ms, 2),
        "success": success,
        **(extra or {}),
    }
    perf_logger.handle(record)


def _record_perf(operation_name: str, elapsed: float, success: bool = True) -> None:
    record_perf_data = {}
    try:
        mem_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        record_perf_data["memory_rss_kb"] = mem_kb
    except Exception:
        pass
    record_performance(operation_name, elapsed * 1000, success=success, extra=record_perf_data or None)
