"""
基金画像解析服务：根据 akshare 基金基本信息进行三级分类判定。
"""
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class FundProfile:
    fund_code: str
    fund_type: str  # 标准化分类标签
    fund_name: str = ""
    fund_size: Optional[float] = None  # 规模（亿元）
    manager: str = ""
    benchmark: str = ""
    strategy_keywords: list[str] = field(default_factory=list)
    skip_prediction: bool = False  # 货币基金跳过预测
    raw_info: dict = field(default_factory=dict)


def classify_fund(fund_code: str) -> FundProfile:
    """三级分类判定：基金类型 → 业绩比较基准 → 默认偏股"""
    try:
        import akshare as ak
        info = ak.fund_individual_basic_info_xq(symbol=fund_code)
    except Exception as exc:
        logger.warning("fund_profile_fetch_failed fund_code=%s reason=%s", fund_code, exc)
        return FundProfile(fund_code=fund_code, fund_type="hybrid_equity")

    raw_type = str(info.get("基金类型", ""))
    benchmark = str(info.get("业绩比较基准", ""))
    strategy = str(info.get("投资策略", ""))
    fund_name = str(info.get("基金简称", ""))

    fund_type = _classify_by_type(raw_type)
    if fund_type == "unknown":
        fund_type = _classify_by_benchmark(benchmark)

    size = _parse_size(info.get("最新规模"))
    manager = str(info.get("基金经理", ""))
    keywords = _extract_strategy_keywords(strategy)
    skip = (fund_type == "money_market")

    logger.info(
        "fund_classified fund_code=%s type=%s name=%s size=%s",
        fund_code, fund_type, fund_name, size,
    )

    return FundProfile(
        fund_code=fund_code,
        fund_type=fund_type,
        fund_name=fund_name,
        fund_size=size,
        manager=manager,
        benchmark=benchmark,
        strategy_keywords=keywords,
        skip_prediction=skip,
        raw_info=info,
    )


def _classify_by_type(raw_type: str) -> str:
    t = raw_type.lower()
    if "货币" in raw_type:
        return "money_market"
    if "指数" in raw_type or "etf" in t:
        return "index_equity" if "债" not in raw_type else "index_bond"
    if "债券" in raw_type:
        if "可转债" in raw_type:
            return "bond_convertible"
        if "纯债" in raw_type:
            return "bond_pure"
        return "bond_mixed"
    if "混合" in raw_type:
        if "偏股" in raw_type:
            return "hybrid_equity"
        if "偏债" in raw_type:
            return "hybrid_bond"
        if "平衡" in raw_type:
            return "hybrid_balanced"
        if "灵活" in raw_type:
            return "hybrid_flexible"
        return "hybrid_equity"
    if "股票" in raw_type:
        return "equity_active"
    if "fof" in t or "基金中基金" in raw_type:
        return "fof"
    if "qdii" in t:
        return "qdii"
    return "unknown"


def _classify_by_benchmark(benchmark: str) -> str:
    if "沪深300" in benchmark or "中证500" in benchmark or "中证800" in benchmark:
        return "hybrid_equity"
    if "中债" in benchmark or "国债" in benchmark:
        return "bond_pure"
    return "hybrid_equity"


def _extract_strategy_keywords(strategy: str) -> list[str]:
    kw = []
    for word in ["成长", "价值", "大盘", "小盘", "医药", "科技", "消费", "新能源", "红利"]:
        if word in strategy:
            kw.append(word)
    return kw


def _parse_size(size_str) -> Optional[float]:
    if not size_str:
        return None
    try:
        s = str(size_str).replace("亿", "").replace("元", "").strip()
        return float(s)
    except (ValueError, TypeError):
        return None