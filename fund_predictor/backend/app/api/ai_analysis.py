"""
AI 分析 API 接口：提供3个端点
1. GET /api/v1/fund/{code}/ai-analysis - 获取AI分析（含新闻）
2. GET /api/v1/fund/{code}/news - 获取基金相关新闻列表
3. GET /api/v1/ai/provider-status - AI Provider 可用性检测
"""
import logging

from fastapi import APIRouter, Query

from app.core.errors import AIProviderError
from app.core.logging_config import set_log_context, request_id_var
from app.services.ai_analysis_service import get_analysis, get_news, get_provider_status

router = APIRouter(prefix="/api/v1", tags=["ai_analysis"])
logger = logging.getLogger(__name__)


@router.get("/fund/{fund_code}/ai-analysis")
async def ai_analysis(
    fund_code: str,
    estimation_return: float = Query(..., description="当前估算/预测收益率"),
    lower_bound: float = Query(..., description="置信区间下界"),
    upper_bound: float = Query(..., description="置信区间上界"),
    source: str = Query(default="intraday", description="分析来源：intraday 或 predict"),
    refresh: bool = Query(default=False, description="是否强制刷新缓存"),
):
    """获取基金 AI 分析（含新闻）

    在已有的 Intraday 或 Predict 结果基础上，异步调用 AI Provider 生成自然语言分析报告。
    支持当日缓存，避免重复计费。

    Args:
        fund_code: 基金代码
        estimation_return: 当前盘中/T+1预测收益率（来自估算或预测结果）
        lower_bound: 置信区间下界
        upper_bound: 置信区间上界
        source: 分析来源，`intraday` 或 `predict`
        refresh: 是否强制刷新（忽略当日缓存）

    Returns:
        AI 分析结果，包含 analysis、news_used、holdings_data_info 等
    """
    set_log_context(fund_code=fund_code, stage="ai_analysis_api")

    try:
        result = await get_analysis(
            fund_code=fund_code,
            estimation_return=estimation_return,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            source=source,
            refresh=refresh,
        )

        return {"ok": True, "data": result}

    except AIProviderError as e:
        logger.error(
            "ai_analysis_error fund_code=%s provider=%s error=%s",
            fund_code, e.provider, e.message
        )

        # 降级响应：尝试返回仅新闻结果
        try:
            news_only = await get_news(fund_code, limit=5)
            return {
                "ok": False,
                "error": {
                    "code": e.code,
                    "message": e.message,
                    "status": e.http_status,
                    "fallback": {
                        "news_only": True,
                        "news_items": news_only.get("news", []),
                    },
                },
            }
        except Exception:
            return {
                "ok": False,
                "error": {
                    "code": e.code,
                    "message": e.message,
                    "status": e.http_status,
                },
            }

    except Exception as e:
        set_log_context(stage="ai_analysis_unexpected_error")
        logger.exception("ai_analysis_unexpected_error fund_code=%s", fund_code)

        return {
            "ok": False,
            "error": {
                "code": "AI_ANALYSIS_ERROR",
                "message": f"AI 分析失败: {str(e)}",
                "status": 500,
            },
        }


@router.get("/fund/{fund_code}/news")
async def fund_news(
    fund_code: str,
    limit: int = Query(default=5, ge=1, le=10, description="返回新闻条数"),
    source: str = Query(default="all", description="新闻来源：cls/em/all"),
):
    """获取基金相关新闻列表

    仅获取新闻列表，不调用 AI，响应更快（约 1-3s）。

    Args:
        fund_code: 基金代码
        limit: 返回新闻条数（最多 10）
        source: 新闻来源过滤：`cls`（财联社）/ `em`（东方财富）/ `all`

    Returns:
        新闻列表及元数据
    """
    set_log_context(fund_code=fund_code, stage="news_api")

    try:
        result = await get_news(fund_code=fund_code, limit=limit, source=source)
        return {"ok": True, "data": result}

    except Exception as e:
        set_log_context(stage="news_api_error")
        logger.exception("news_fetch_error fund_code=%s error=%s", fund_code, e)

        return {
            "ok": True,
            "data": {
                "fund_code": fund_code,
                "news": [],
                "total": 0,
                "fetched_at": None,
                "error": f"新闻获取失败: {str(e)}",
            },
        }


@router.get("/ai/provider-status")
async def provider_status():
    """检测 AI Provider 可用性

    用于前端展示状态和 AdminDataStatus 页面。
    检测主 Provider 和备用 Provider 的连接状态、延迟等信息。

    Returns:
        Provider 状态信息字典
    """
    set_log_context(stage="provider_status_api")

    try:
        result = await get_provider_status()
        return {"ok": True, "data": result}

    except Exception as e:
        set_log_context(stage="provider_status_error")
        logger.exception("provider_status_check_error error=%s", e)

        return {
            "ok": False,
            "error": {
                "code": "PROVIDER_STATUS_ERROR",
                "message": f"Provider 状态检测失败: {str(e)}",
                "status": 500,
            },
        }
