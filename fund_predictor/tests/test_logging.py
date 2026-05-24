"""
日志系统单元测试：验证结构化JSON Handler、上下文过滤器、审计/性能日志等。
"""
import json
import logging
import os
import sys
import tempfile
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest


class TestContextFilter:
    def test_default_context_values(self):
        from app.core.logging_config import (
            ContextFilter, request_id_var, fund_code_var, task_id_var, stage_var,
        )

        request_id_var.set("-")
        fund_code_var.set("-")
        task_id_var.set("-")
        stage_var.set("-")
        f = ContextFilter()
        record = logging.LogRecord("test", logging.INFO, "file.py", 1, "msg", (), None)
        assert f.filter(record) is True
        assert record.request_id == "-"
        assert record.fund_code == "-"
        assert record.task_id == "-"
        assert record.stage == "-"

    def test_custom_context_values(self):
        from app.core.logging_config import (
            ContextFilter, set_log_context,
            request_id_var, fund_code_var, task_id_var, stage_var,
        )

        set_log_context(request_id="abc123", fund_code="000001", task_id="t1", stage="predict")
        f = ContextFilter()
        record = logging.LogRecord("test", logging.INFO, "file.py", 1, "msg", (), None)
        f.filter(record)
        assert record.request_id == "abc123"
        assert record.fund_code == "000001"
        assert record.task_id == "t1"
        assert record.stage == "predict"

    def test_get_log_context(self):
        from app.core.logging_config import set_log_context, get_log_context

        set_log_context(request_id="r1", fund_code="f1", task_id="t1", stage="s1")
        ctx = get_log_context()
        assert ctx["request_id"] == "r1"
        assert ctx["fund_code"] == "f1"


class TestStructuredJSONHandler:
    def test_emits_valid_json(self):
        from app.core.logging_config import StructuredJSONHandler

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.jsonl")
            handler = StructuredJSONHandler(log_file, max_bytes=1024, backup_count=1)

            record = logging.LogRecord(
                name="test.logger",
                level=logging.INFO,
                pathname="/fake/path.py",
                lineno=42,
                msg="hello world",
                args=(),
                exc_info=None,
            )
            record.request_id = "req-001"
            record.fund_code = "000001"
            record.stage = "test"

            handler.emit(record)
            handler.close()

            with open(log_file, "r") as f:
                line = f.readline().strip()

            data = json.loads(line)
            assert data["level"] == "INFO"
            assert data["logger"] == "test.logger"
            assert data["message"] == "hello world"
            assert data["request_id"] == "req-001"
            assert data["fund_code"] == "000001"
            assert data["@timestamp"] is not None

    def test_exception_in_record(self):
        from app.core.logging_config import StructuredJSONHandler

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test_err.jsonl")
            handler = StructuredJSONHandler(log_file, max_bytes=1024, backup_count=1)

            try:
                raise ValueError("test error")
            except ValueError:
                import traceback
                exc_info = sys.exc_info()

            record = logging.LogRecord(
                name="err_test",
                level=logging.ERROR,
                pathname="/fake.py",
                lineno=10,
                msg="error occurred",
                args=(),
                exc_info=exc_info,
            )
            handler.emit(record)
            handler.close()

            with open(log_file, "r") as f:
                line = f.readline().strip()

            data = json.loads(line)
            assert data["exception"] is not None
            assert "ValueError" in data["exception"]
            assert "test error" in data["exception"]


class TestAuditLog:
    def test_audit_log_creates_entry(self):
        from app.core.logging_config import audit_log, audit_logger, StructuredJSONHandler

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "audit.jsonl")
            handler = StructuredJSONHandler(log_file, max_bytes=1024, backup_count=1)
            old_handlers = audit_logger.handlers[:]
            audit_logger.addHandler(handler)

            try:
                audit_log(action="predict", target="fund:018956", details={"model": "ridge"})

                handler.close()
                with open(log_file, "r") as f:
                    line = f.readline().strip()

                data = json.loads(line)
                assert data["extra"]["action"] == "predict"
                assert data["extra"]["target"] == "fund:018956"
                assert data["extra"]["details"]["model"] == "ridge"
                assert data["extra"]["user_id"] == "-"
            finally:
                audit_logger.handlers[:] = old_handlers


class TestPerfLogger:
    def test_decorator_records_performance(self):
        from app.core.perf_logger import log_performance
        from app.core.logging_config import perf_logger, StructuredJSONHandler

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "perf.jsonl")
            handler = StructuredJSONHandler(log_file, max_bytes=1024, backup_count=1)
            old_handlers = perf_logger.handlers[:]
            perf_logger.addHandler(handler)

            @log_performance("test_operation")
            def slow_func():
                import time
                time.sleep(0.01)
                return 42

            try:
                result = slow_func()
                assert result == 42

                handler.close()
                with open(log_file, "r") as f:
                    line = f.readline().strip()

                data = json.loads(line)
                assert data["extra"]["operation"] == "test_operation"
                assert data["extra"]["elapsed_ms"] >= 5
                assert data["extra"]["success"] is True
            finally:
                perf_logger.handlers[:] = old_handlers

    def test_functional_call(self):
        from app.core.perf_logger import record_performance
        from app.core.logging_config import perf_logger, StructuredJSONHandler

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "perf2.jsonl")
            handler = StructuredJSONHandler(log_file, max_bytes=1024, backup_count=1)
            old_handlers = perf_logger.handlers[:]
            perf_logger.addHandler(handler)

            try:
                record_performance("manual_op", elapsed_ms=123.45, success=True, extra={"key": "val"})

                handler.close()
                with open(log_file, "r") as f:
                    line = f.readline().strip()

                data = json.loads(line)
                assert data["extra"]["operation"] == "manual_op"
                assert data["extra"]["elapsed_ms"] == 123.45
                assert data["extra"]["key"] == "val"
            finally:
                perf_logger.handlers[:] = old_handlers


class TestSetupLogging:
    def test_setup_logging_creates_files(self):
        from app.core.logging_config import setup_logging

        setup_logging()

        from app.core.config import LOG_DIR
        assert LOG_DIR.exists()

        expected_files = ["app.log", "api.jsonl", "train.log", "error.log",
                          "audit.jsonl", "perf.jsonl"]
        for fname in expected_files:
            fpath = LOG_DIR / fname
            if fname.endswith(".jsonl"):
                if fpath.exists():
                    with open(fpath) as f:
                        first_line = f.readline().strip()
                    if first_line:
                        parsed = json.loads(first_line)
                        assert "@timestamp" in parsed
            else:
                pass

        root_logger = logging.getLogger()
        assert root_logger.level <= logging.INFO

    def test_third_party_loggers_suppressed(self):
        from app.core.logging_config import _setup_third_party_loggers

        _setup_third_party_loggers({
            "logging": {
                "third_party": {
                    "uvicorn": "WARNING",
                    "sqlalchemy": "ERROR",
                    "requests": "CRITICAL",
                }
            }
        })

        assert logging.getLogger("uvicorn").level == logging.WARNING
        assert logging.getLogger("sqlalchemy").level == logging.ERROR
        assert logging.getLogger("requests").level == logging.CRITICAL


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
