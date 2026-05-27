"""
分类路由引擎：根据基金类型分发到对应的预测流水线。

阶段1：偏股类走现有成熟流程；其他类型走通用流程（后续阶段逐步替换为专用流水线）。
"""
import logging

from app.services.fund_profile_service import FundProfile
from app.services.prediction_service import predict_next as generic_predict

logger = logging.getLogger(__name__)


def route_predict(fund_code: str, profile: FundProfile, request_id: str) -> dict:
    """根据基金类型路由到对应预测流水线"""

    if profile.skip_prediction:
        return {
            "fund_code": fund_code,
            "fund_type": profile.fund_type,
            "message": "货币基金净值恒为1，无需预测",
            "prediction_mode": "N/A",
            "fund_profile": {
                "type": profile.fund_type,
                "name": profile.fund_name,
                "size": profile.fund_size,
            },
        }

    # 阶段1：偏股类走现有成熟流程；其余类型走通用流程（后续阶段逐步替换）
    if profile.fund_type in ("hybrid_equity", "equity_active"):
        logger.info("routing=%s fund_code=%s", profile.fund_type, fund_code)
        result = generic_predict(fund_code, request_id)
    elif profile.fund_type == "index_equity":
        from app.rules.index_rule_engine import predict_index_fund, get_index_mapping
        from app.services.feature_service import build_features
        
        try:
            df, _, _ = build_features(fund_code, require_fresh=False)
            
            # 获取最新一期指数收益率作为预测依据
            index_ret_col = None
            for col in ["hs300_ret", "zz500_ret", "zz1000_ret"]:
                if col in df.columns:
                    index_ret_col = col
                    break
            
            if index_ret_col is not None and len(df) > 0:
                latest_index_ret = df[index_ret_col].iloc[-1]
                rule_result = predict_index_fund(
                    fund_code=fund_code,
                    index_return=latest_index_ret,
                )
                
                result = {
                    "fund_code": fund_code,
                    "fund_type": "index_equity",
                    "predicted_return": rule_result.predicted_return,
                    "confidence_interval": [rule_result.lower_bound, rule_result.upper_bound],
                    "prediction_mode": "rule_based",
                    "method": rule_result.method,
                    "index_return": rule_result.index_return,
                }
            else:
                logger.warning("index_equity_no_index_data fund_code=%s", fund_code)
                result = generic_predict(fund_code, request_id)
                
        except Exception as e:
            logger.exception("index_rule_failed fund_code=%s error=%s", fund_code, e)
            result = generic_predict(fund_code, request_id)
    else:
        # 债券、灵活配置、FOF、QDII 暂走通用流程
        logger.info("routing=%s (generic fallback) fund_code=%s", profile.fund_type, fund_code)
        result = generic_predict(fund_code, request_id)

    # 附加基金画像信息
    result["fund_profile"] = {
        "type": profile.fund_type,
        "name": profile.fund_name,
        "size": profile.fund_size,
        "manager": profile.manager,
        "benchmark": profile.benchmark,
        "strategy_keywords": profile.strategy_keywords,
    }
    result["fund_type"] = profile.fund_type

    return result