import re
import logging

logger = logging.getLogger(__name__)

BENCHMARK_PATTERNS = [
    (r"沪深300.*?(\d+)%", lambda m: ("hybrid_equity", 0.95) if int(m.group(1)) >= 65 else None),
    (r"中证500.*?(\d+)%", lambda m: ("equity_active", 0.95) if int(m.group(1)) >= 65 else None),
    (r"中债.*综合", lambda _: ("bond_pure", 0.95)),
    (r"中证全债", lambda _: ("bond_pure", 0.95)),
    (r"中证转债", lambda _: ("bond_convertible", 0.95)),
    (r"沪深300.*50%.*中债.*50%", lambda _: ("hybrid_balanced", 0.95)),
]

FUND_TYPE_MAP = {
    "混合型-偏股": "hybrid_equity",
    "股票型": "equity_active",
    "债券型-纯债": "bond_pure",
    "债券型-混合债": "bond_mixed",
    "债券型-可转债": "bond_convertible",
    "指数型-股票": "index_equity",
    "指数型-债券": "index_bond",
    "混合型-灵活": "hybrid_flexible",
    "混合型-偏债": "hybrid_bond",
    "FOF": "fof",
    "QDII": "qdii",
    "货币型": "money_market",
}


def classify(fund_name: str = "", fund_type_raw: str = "", benchmark: str = "", invest_strategy: str = "") -> dict:
    for pattern, handler in BENCHMARK_PATTERNS:
        m = re.search(pattern, benchmark)
        if m:
            result = handler(m)
            if result:
                return {"fund_type": result[0], "confidence": result[1], "level": 1}
    if fund_type_raw in FUND_TYPE_MAP:
        return {"fund_type": FUND_TYPE_MAP[fund_type_raw], "confidence": 0.88, "level": 2}
    for key, val in FUND_TYPE_MAP.items():
        if key in fund_type_raw or key in fund_name:
            return {"fund_type": val, "confidence": 0.65, "level": 2}
    combined = invest_strategy + fund_name
    if "成长" in combined or "股票" in combined:
        return {"fund_type": "equity_active", "confidence": 0.55, "level": 3}
    if "债券" in combined or "债" in combined:
        return {"fund_type": "bond_pure", "confidence": 0.55, "level": 3}
    if "货币" in combined:
        return {"fund_type": "money_market", "confidence": 0.55, "level": 3}
    return {"fund_type": "hybrid_equity", "confidence": 0.50, "level": 3, "default": True}