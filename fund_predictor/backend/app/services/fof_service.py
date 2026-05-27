import logging
from datetime import datetime

import numpy as np
import pandas as pd

from app.core.logging_config import set_log_context
from app.services.fund_profile_service import classify_fund, FundProfile
from app.services.holding_service import get_fund_holdings
from app.services.routing_service import route_predict

logger = logging.getLogger(__name__)

MAX_FOF_RECURSION_DEPTH = 3
FOF_SUBFUND_COL = "基金代码"
FOF_WEIGHT_COL = "占净值比例"


def _is_fof_fund(profile: FundProfile) -> bool:
    """判断是否为FOF基金"""
    return profile.fund_type == "fof" or "fof" in (profile.strategy_keywords or "").lower()


def _extract_subfund_holdings(holdings_df: pd.DataFrame) -> list[dict]:
    """
    从持仓数据中提取子基金持仓信息。

    FOF基金的持仓是其他基金（而非股票），需要特殊处理。
    """
    subfunds = []
    if holdings_df.empty:
        return subfunds

    code_col = None
    weight_col = None
    name_col = None

    for col in holdings_df.columns:
        col_str = str(col).strip()
        if "基金代码" in col_str or col_str == "stock_code":
            code_col = col
        elif "占净值比例" in col_str or col_str == "weight_nav":
            weight_col = col
        elif "基金名称" in col_str or col_str == "stock_name":
            name_col = col

    if not code_col or not weight_col:
        logger.warning("fof_holdings_columns_missing available_cols=%s", list(holdings_df.columns))
        return subfunds

    latest_date = holdings_df["report_date"].max() if "report_date" in holdings_df.columns else None
    if latest_date:
        holdings_df = holdings_df[holdings_df["report_date"] == latest_date]

    for _, row in holdings_df.iterrows():
        code = str(row[code_col]).strip().zfill(6)
        try:
            weight = float(row[weight_col]) / 100.0 if pd.notna(row[weight_col]) else 0.0
        except (ValueError, TypeError):
            weight = 0.0
        name = str(row[name_col]).strip() if name_col and pd.notna(row.get(name_col)) else ""
        if code and weight > 0:
            subfunds.append({
                "subfund_code": code,
                "subfund_name": name,
                "weight": round(weight, 6),
            })

    subfunds.sort(key=lambda x: x["weight"], reverse=True)
    return subfunds


def predict_fof(fund_code: str, request_id: str) -> dict:
    """
    FOF递归预测服务。

    获取FOF子基金持仓，对每个子基金递归调用routing_service.route_predict，
    按持仓权重加权汇总，返回子基金预测详情 + 加权汇总结果。

    支持嵌套FOF（FOF-of-FOF），最大递归深度为3层。

    Args:
        fund_code: FOF基金代码
        request_id: 请求ID（用于日志追踪）

    Returns:
        包含以下字段的字典：
        - fund_code: 基金代码
        - is_fof: 是否识别为FOF
        - subfunds: 子基金预测详情列表
        - weighted_prediction: 加权汇总预测结果
        - total_weight: 总权重（应接近1.0）
        - recursion_depth: 当前递归深度
        - predicted_at: 预测时间
    """
    return _predict_fof_recursive(fund_code, request_id, depth=1)


def _predict_fof_recursive(fund_code: str, request_id: str, depth: int) -> dict:
    """FOF递归预测的内部实现，带深度控制"""
    set_log_context(fund_code=fund_code, stage="fof_predict_start", fof_depth=depth)
    logger.info("fof_predict_start fund_code=%s depth=%s", fund_code, depth)

    result = {
        "fund_code": fund_code,
        "depth": depth,
        "predicted_at": datetime.now().isoformat(timespec="seconds"),
        "is_fof": False,
        "subfunds": [],
        "weighted_prediction": None,
        "total_weight": 0.0,
        "errors": [],
    }

    try:
        profile = classify_fund(fund_code)

        if not _is_fof_fund(profile):
            logger.info("fof_not_fof_fund fund_code=%s type=%s", fund_code, profile.fund_type)

            direct_result = route_predict(fund_code, profile, request_id)
            result["direct_prediction"] = direct_result
            result["is_fof"] = False
            return result

        result["is_fof"] = True
        result["fund_profile"] = {
            "type": profile.fund_type,
            "name": profile.fund_name,
            "strategy_keywords": profile.strategy_keywords,
        }

        holdings_df, holding_meta = get_fund_holdings(fund_code)
        if holdings_df.empty:
            msg = f"无法获取FOF持仓数据: {holding_meta.get('reason', 'unknown')}"
            logger.warning("fof_no_holdings fund_code=%s reason=%s", fund_code, msg)
            result["errors"].append({"stage": "holdings", "message": msg})
            return result

        subfunds = _extract_subfund_holdings(holdings_df)
        if not subfunds:
            msg = "未从持仓数据中提取到有效子基金"
            logger.warning("fof_no_subfunds fund_code=%s", fund_code)
            result["errors"].append({"stage": "extraction", "message": msg})
            return result

        logger.info("fof_subfunds_found fund_code=%s count=%s", fund_code, len(subfunds))

        weighted_pred_sum = 0.0
        total_weight = 0.0
        valid_count = 0

        for sub in subfunds:
            sub_code = sub["subfund_code"]
            sub_weight = sub["weight"]

            sub_result = {
                **sub,
                "prediction_status": "pending",
                "prediction_detail": None,
                "weighted_contribution": 0.0,
            }

            try:
                if depth < MAX_FOF_RECURSION_DEPTH:

                    sub_profile = classify_fund(sub_code)
                    if _is_fof_fund(sub_profile):
                        logger.info(
                            "fof_nested_fof_detected subfund=%s parent=%s depth=%s",
                            sub_code, fund_code, depth + 1,
                        )
                        nested = _predict_fof_recursive(sub_code, request_id, depth=depth + 1)
                        sub_result["prediction_detail"] = nested
                        sub_result["prediction_status"] = "nested_fof"

                        nested_weighted = nested.get("weighted_prediction")
                        if nested_weighted and isinstance(nested_weighted, (int, float)):
                            pred_val = float(nested_weighted)
                        elif isinstance(nested_weighted, dict):
                            pred_val = float(nested_weighted.get("predicted_value", 0))
                        else:
                            pred_val = 0.0
                    else:
                        sub_pred = route_predict(sub_code, classify_fund(sub_code), request_id)
                        sub_result["prediction_detail"] = sub_pred
                        sub_result["prediction_status"] = "success"
                        pred_val = _extract_prediction_value(sub_pred)
                else:
                    sub_pred = route_predict(sub_code, classify_fund(sub_code), request_id)
                    sub_result["prediction_detail"] = sub_pred
                    sub_result["prediction_status"] = "success (depth_limit)"
                    pred_val = _extract_prediction_value(sub_pred)

                contribution = pred_val * sub_weight
                sub_result["weighted_contribution"] = round(contribution, 8)
                weighted_pred_sum += contribution
                total_weight += sub_weight
                valid_count += 1

                logger.info(
                    "fof_subfund_predicted subfund=%s weight=%.4f pred=%.6f contrib=%.8s",
                    sub_code, sub_weight, pred_val, contribution,
                )

            except Exception as e:
                logger.exception("fof_subfund_failed subfund=%s error=%s", sub_code, e)
                sub_result["prediction_status"] = "failed"
                sub_result["error"] = str(e)
                result["errors"].append({
                    "stage": "subfund_prediction",
                    "subfund_code": sub_code,
                    "error": str(e),
                })

            result["subfunds"].append(sub_result)

        result["total_weight"] = round(total_weight, 6)
        result["valid_subfund_count"] = valid_count

        if valid_count > 0 and total_weight > 0:
            normalized_weighted = weighted_pred_sum / total_weight if total_weight != 1.0 else weighted_pred_sum
            result["weighted_prediction"] = {
                "value": round(normalized_weighted, 6),
                "raw_sum": round(weighted_pred_sum, 8),
                "method": "weighted_average",
                "normalization_applied": abs(total_weight - 1.0) > 0.01,
            }
        else:
            result["errors"].append({"stage": "aggregation", "message": "无有效子基金预测"})

        set_log_context(stage="fof_predict_success")
        logger.info(
            "fof_predict_success fund_code=%s subfunds=%s valid=%s total_weight=%.4f final_pred=%.6s",
            fund_code, len(subfunds), valid_count, total_weight, result.get("weighted_prediction"),
        )
        return result

    except Exception as e:
        set_log_context(stage="fof_predict_failed")
        logger.exception("fof_predict_failed fund_code=%s depth=%s error=%s", fund_code, depth, e)
        result["errors"].append({"stage": "top_level", "error": str(e)})
        return result


def _extract_prediction_value(pred_result: dict) -> float:
    """
    从路由预测结果中提取数值型预测值。
    兼容多种返回格式。
    """
    if not pred_result or not isinstance(pred_result, dict):
        return 0.0

    candidates = [
        pred_result.get("predicted_value"),
        pred_result.get("prediction"),
        pred_result.get("estimated_return"),
        pred_result.get("point_estimate"),
        pred_result.get("interval_center"),
    ]

    for val in candidates:
        if val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                continue

    data = pred_result.get("data") or {}
    if isinstance(data, dict):
        for key in ("predicted_value", "prediction", "point_estimate"):
            val = data.get(key)
            if val is not None:
                try:
                    return float(val)
                except (ValueError, TypeError):
                    continue

    return 0.0


def get_fof_summary(fund_code: str, request_id: str) -> dict:
    """
    获取FOF预测摘要，用于前端展示。

    简化版输出，只包含关键聚合指标。
    """
    full_result = predict_fof(fund_code, request_id)

    summary = {
        "fund_code": fund_code,
        "is_fof": full_result.get("is_fof", False),
        "subfund_count": len(full_result.get("subfunds", [])),
        "valid_predictions": full_result.get("valid_subfund_count", 0),
        "total_weight": full_result.get("total_weight", 0.0),
        "has_errors": len(full_result.get("errors", [])) > 0,
        "predicted_at": full_result.get("predicted_at"),
    }

    wp = full_result.get("weighted_prediction")
    if wp and isinstance(wp, dict):
        summary["weighted_prediction_value"] = wp.get("value")

    top_subfunds = sorted(
        [s for s in full_result.get("subfunds", []) if s.get("prediction_status") == "success"],
        key=lambda x: x.get("weight", 0), reverse=True,
    )[:5]
    summary["top_subfunds"] = [
        {
            "code": s["subfund_code"],
            "name": s.get("subfund_name", ""),
            "weight": s["weight"],
            "status": s.get("prediction_status"),
        }
        for s in top_subfunds
    ]

    return summary
