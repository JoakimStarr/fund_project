import time
import uuid
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
        request.state.request_id = request_id
        start_time = time.time()
        response = await call_next(request)
        elapsed = time.time() - start_time
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{elapsed*1000:.0f}ms"
        perf_logger = logging.getLogger("perf")
        if perf_logger.isEnabledFor(logging.INFO):
            perf_logger.info("api_perf", extra={"extra_fields": {
                "request_id": request_id, "method": request.method,
                "path": request.url.path, "status": response.status_code,
                "elapsed_ms": round(elapsed*1000, 1)
            }})
        return response

def setup_cors(app):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

def setup_middleware(app):
    setup_cors(app)
    app.add_middleware(RequestContextMiddleware)