import logging

from fastapi import APIRouter, Query

from app.core.errors import AppError, NotFoundError
from app.core.logging_config import set_log_context
from app.services.intraday_service import estimate_intraday_nav, get_latest_intraday_estimate

router = APIRouter(prefix="/api/v1/fund", tags=["intraday"])
logger = logging.getLogger(__name__)


class IntradayEstimateError(AppError):
    code = "INTRADAY_ESTIMATE_FAILED"
    stage = "intraday_estimation"
    http_status = 500


@router.post("/{fund_code}/intraday")
def trigger_intraday_estimate(fund_code: str):
    """
    触发T日盘中净值估算。

    执行双路径融合估算（持仓映射 + 指数回归），
    返回估算净值、各路径收益、融合权重和置信度。
    """
    fund_code = fund_code.strip()
    set_log_context(fund_code=fund_code)
    logger.info("api_intraday_trigger fund_code=%s", fund_code)

    try:
        result = estimate_intraday_nav(fund_code)

        if not result.get("ok", True) and "error" in result:
            raise IntradayEstimateError(
                f"盘中估算失败: {result['error']}",
                details={"fund_code": fund_code, "raw_error": result["error"]},
            )

        return {
            "ok": True,
            "data": {
                "fund_code": result["fund_code"],
                "last_nav": result.get("last_nav"),
                "last_date": result.get("last_date"),
                "estimated_nav": result.get("estimated_nav"),
                "estimated_change_pct": result.get("estimated_change_pct"),
                "holding_path_return": result.get("holding_path_return"),
                "index_path_return": result.get("index_path_return"),
                "fusion_weight": result.get("fusion_weight"),
                "confidence": result.get("confidence"),
                "holding_meta": _sanitize_for_response(result.get("holding_path_meta")),
                "index_meta": _sanitize_for_response(result.get("index_path_meta")),
                "estimated_at": result.get("estimated_at"),
            },
        }
    except AppError:
        raise
    except Exception as e:
        logger.exception("api_intraday_error fund_code=%s", fund_code)
        raise IntradayEstimateError(
            f"盘中估算异常: {str(e)}",
            details={"fund_code": fund_code, "error": str(e)},
        ) from e


@router.get("/{fund_code}/intraday/latest")
def get_intraday_latest(
    fund_code: str,
    auto_estimate: bool = Query(True, description="缓存为空时是否自动触发估算（默认开启）"),
    force_refresh: bool = Query(False, description="是否强制重新计算"),
):
    """
    获取最新盘中估算结果。

    优先级：
    1. force_refresh=true → 强制重新计算
    2. 缓存命中 → 直接返回缓存
    3. 缓存未命中 + auto_estimate=true → 自动触发估算并返回
    4. 缓存未命中 + auto_estimate=false → 返回404提示手动触发
    """
    fund_code = fund_code.strip()
    set_log_context(fund_code=fund_code)

    if force_refresh:
        logger.info("api_intraday_force_refresh fund_code=%s", fund_code)
        try:
            result = estimate_intraday_nav(fund_code)
            if not result.get("ok", True) and "error" in result:
                raise IntradayEstimateError(
                    f"盘中估算失败: {result['error']}",
                    details={"fund_code": fund_code},
                )
            return {
                "ok": True,
                "data": {
                    "fund_code": result["fund_code"],
                    "estimated_nav": result.get("estimated_nav"),
                    "estimated_change_pct": result.get("estimated_change_pct"),
                    "holding_path_return": result.get("holding_path_return"),
                    "index_path_return": result.get("index_path_return"),
                    "fusion_weight": result.get("fusion_weight"),
                    "confidence": result.get("confidence"),
                    "from_cache": False,
                    "estimated_at": result.get("estimated_at"),
                },
            }
        except AppError:
            raise
        except Exception as e:
            logger.exception("api_intraday_refresh_error fund_code=%s", fund_code)
            raise IntradayEstimateError(f"强制刷新失败: {str(e)}", details={"fund_code": fund_code}) from e

    cached = get_latest_intraday_estimate(fund_code)
    if cached is None:
        if auto_estimate:
            logger.info("api_intraday_auto_estimate fund_code=%s (cache miss, triggering estimation)", fund_code)
            try:
                result = estimate_intraday_nav(fund_code)
                if not result.get("ok", True) and "error" in result:
                    raise IntradayEstimateError(
                        f"盘中估算失败: {result['error']}",
                        details={"fund_code": fund_code},
                    )
                logger.info("api_intraday_auto_estimate_success fund_code=%s", fund_code)
                return {
                    "ok": True,
                    "data": {
                        "fund_code": result["fund_code"],
                        "last_nav": result.get("last_nav"),
                        "last_date": result.get("last_date"),
                        "estimated_nav": result.get("estimated_nav"),
                        "estimated_change_pct": result.get("estimated_change_pct"),
                        "holding_path_return": result.get("holding_path_return"),
                        "index_path_return": result.get("index_path_return"),
                        "fusion_weight": result.get("fusion_weight"),
                        "confidence": result.get("confidence"),
                        "from_cache": False,
                        "auto_triggered": True,
                        "estimated_at": result.get("estimated_at"),
                    },
                }
            except AppError:
                raise
            except Exception as e:
                logger.exception("api_intraday_auto_estimate_error fund_code=%s", fund_code)
                raise IntradayEstimateError(
                    f"自动估算失败: {str(e)}",
                    details={
                        "fund_code": fund_code,
                        "hint": f"可尝试手动调用 POST /api/v1/fund/{fund_code}/intraday",
                    }
                ) from e
        else:
            raise NotFoundError(
                "暂无盘中估算数据，请先调用POST接口触发估算",
                details={"fund_code": fund_code, "hint": f"POST /api/v1/fund/{fund_code}/intraday"},
            )

    logger.info("api_intraday_cache_hit fund_code=%s", fund_code)
    return {
        "ok": True,
        "data": {
            "fund_code": cached["fund_code"],
            "last_nav": cached.get("last_nav"),
            "last_date": cached.get("last_date"),
            "estimated_nav": cached.get("estimated_nav"),
            "estimated_change_pct": cached.get("estimated_change_pct"),
            "holding_path_return": cached.get("holding_path_return"),
            "index_path_return": cached.get("index_path_return"),
            "fusion_weight": cached.get("fusion_weight"),
            "confidence": cached.get("confidence"),
            "from_cache": True,
            "estimated_at": cached.get("estimated_at"),
        },
    }


def _sanitize_for_response(meta: dict | None) -> dict | None:
    """清理元数据，移除不适合API响应的内部字段"""
    if not meta or not isinstance(meta, dict):
        return None
    safe_keys = {"path", "available", "proxy_status", "proxy_r2", "available_count",
                 "regression_index", "beta", "r2", "window", "latest_index_ret"}
    return {k: v for k, v in meta.items() if k in safe_keys}
