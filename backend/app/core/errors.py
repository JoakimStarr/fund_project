from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code = code
        self.message = message
        self.status = status


class InsufficientDataError(AppError):
    def __init__(self, message="历史数据不足"):
        super().__init__("INSUFFICIENT_DATA", message, 422)


class ModelNotFoundError(AppError):
    def __init__(self, message="模型文件不存在"):
        super().__init__("MODEL_NOT_FOUND", message, 404)


class TrainingError(AppError):
    def __init__(self, message="训练失败"):
        super().__init__("TRAINING_ERROR", message, 500)


class PredictionError(AppError):
    def __init__(self, message="预测计算异常"):
        super().__init__("PREDICTION_ERROR", message, 500)


class DataFetchError(AppError):
    def __init__(self, message="数据获取失败"):
        super().__init__("DATA_FETCH_ERROR", message, 502)


class AIProviderUnavailableError(AppError):
    def __init__(self, message="AI 服务暂时不可用"):
        super().__init__("AI_PROVIDER_UNAVAILABLE", message, 503)


class AINotConfiguredError(AppError):
    def __init__(self, message="AI API Key 未配置"):
        super().__init__("AI_NOT_CONFIGURED", message, 503)


class ValidationError(AppError):
    def __init__(self, message="参数校验失败"):
        super().__init__("VALIDATION_ERROR", message, 422)


async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status,
        content={"ok": False, "error": {"code": exc.code, "message": exc.message, "status": exc.status}},
    )


async def general_error_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"ok": False, "error": {"code": "INTERNAL_ERROR", "message": str(exc), "status": 500}},
    )