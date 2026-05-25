"""
基金画像解析服务：根据 akshare 基金基本信息进行三级分类判定。
支持 SQLite 缓存层：优先读 DB，未命中或过期时从 API 获取并入库。
"""
import json
import logging
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class FundProfile:
    fund_code: str
    fund_type: str
    fund_name: str = ""
    fund_size: Optional[float] = None
    manager: str = ""
    benchmark: str = ""
    strategy_keywords: list[str] = field(default_factory=list)
    skip_prediction: bool = False
    raw_info: dict = field(default_factory=dict)
    fund_type_raw: str = ""
    establish_date: str = ""
    fee_rate: Optional[float] = None
    strategy_text: str = ""
    risk_level: str = ""
    stale: bool = False
    cached_at: str = ""


def _parse_benchmark_weight(benchmark: str | None) -> float | None:
    """解析基准字符串中的股票权重。

    支持格式:
    - "沪深300×80%+中证全债×20%" → 0.80
    - "沪深300收益率*80%+中债*20%" → 0.80
    - "50%+50%" → 0.50
    - 纯文字描述 → None

    Returns:
        股票权重 (0.0~1.0), 无法解析返回 None
    """
    if not benchmark:
        return None

    import re

    patterns = [
        r'(\d+(?:\.\d+)?)\s*[%％]',           # "80%" or "80％"
        r'[\*×]\s*(\d+(?:\.\d+)?)',            # "*80" or "×80"
    ]

    weights = []
    for pattern in patterns:
        matches = re.findall(pattern, benchmark)
        for m in matches:
            try:
                w = float(m) / 100.0
                if 0.0 <= w <= 1.0:
                    weights.append(w)
            except ValueError:
                continue

    if not weights:
        return None

    return max(weights)


def classify_fund(fund_code: str) -> FundProfile:
    try:
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

    if fund_type == "money_market":
        skip = True

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
        fund_type_raw=raw_type,
        strategy_text=strategy,
        risk_level=_risk_level_for_type(fund_type),
    )


def get_profile(fund_code: str, force_refresh: bool = False) -> FundProfile:
    from app.db.database import get_conn

    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM fund_profiles WHERE fund_code=?", [fund_code]
        ).fetchone()

    if row and not force_refresh:
        ttl = row["cache_ttl_days"] or 7
        fetched = row["fetched_at"]
        if _is_fresh(fetched, ttl):
            logger.info("profile_cache_hit fund_code=%s fetched_at=%s", fund_code, fetched)
            return _row_to_profile(dict(row))

    start = datetime.now()
    try:
        profile = classify_fund(fund_code)
        profile.stale = False
        profile.cached_at = datetime.now(timezone.utc).isoformat()

        with get_conn() as conn:
            now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            conn.execute(
                """
                INSERT INTO fund_profiles (
                    fund_code, fund_name, fund_type, fund_type_raw,
                    establish_date, fund_size, manager, fee_rate,
                    benchmark, strategy_text, strategy_keywords,
                    skip_prediction, risk_level,
                    data_source, fetched_at, updated_at, cache_ttl_days, raw_info_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'akshare', ?, ?, 7, ?)
                ON CONFLICT(fund_code) DO UPDATE SET
                    fund_name=excluded.fund_name,
                    fund_type=excluded.fund_type,
                    fund_type_raw=excluded.fund_type_raw,
                    establish_date=excluded.establish_date,
                    fund_size=excluded.fund_size,
                    manager=excluded.manager,
                    fee_rate=excluded.fee_rate,
                    benchmark=excluded.benchmark,
                    strategy_text=excluded.strategy_text,
                    strategy_keywords=excluded.strategy_keywords,
                    skip_prediction=excluded.skip_prediction,
                    risk_level=excluded.risk_level,
                    fetched_at=excluded.fetched_at,
                    updated_at=excluded.updated_at,
                    raw_info_json=excluded.raw_info_json
                """,
                [
                    profile.fund_code, profile.fund_name, profile.fund_type, profile.fund_type_raw,
                    profile.establish_date, profile.fund_size, profile.manager, profile.fee_rate,
                    profile.benchmark, profile.strategy_text,
                    json.dumps(profile.strategy_keywords, ensure_ascii=False),
                    int(profile.skip_prediction), profile.risk_level,
                    now, now,
                    json.dumps(profile.raw_info, ensure_ascii=False, default=str),
                ],
            )
            duration_ms = int((datetime.now() - start).total_seconds() * 1000)
            conn.execute(
                "INSERT INTO data_fetch_log (entity_type, entity_key, source, success, duration_ms, fetched_at) VALUES (?, ?, ?, 1, ?, ?)",
                ["profile", fund_code, "akshare", duration_ms, now],
            )

        logger.info("profile_fetched_and_cached fund_code=%s duration_ms=%s", fund_code, duration_ms)
        return profile
    except Exception as exc:
        logger.exception("profile_fetch_failed fund_code=%s", fund_code)
        if row:
            profile = _row_to_profile(dict(row))
            profile.stale = True
            return profile
        raise


def invalidate_profile_cache(fund_code: str) -> bool:
    from app.db.database import get_conn
    try:
        with get_conn() as conn:
            conn.execute("UPDATE fund_profiles SET fetched_at='1970-01-01' WHERE fund_code=?", [fund_code])
        return True
    except Exception:
        return False


def _is_fresh(fetched_at: str, ttl_days: int) -> bool:
    try:
        dt = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - dt).days
        return age < ttl_days
    except Exception:
        return False


def _row_to_profile(row: dict) -> FundProfile:
    kw_str = row.get("strategy_keywords") or "[]"
    try:
        keywords = json.loads(kw_str)
    except Exception:
        keywords = []
    raw_str = row.get("raw_info_json") or "{}"
    try:
        raw_info = json.loads(raw_str)
    except Exception:
        raw_info = {}
    return FundProfile(
        fund_code=row["fund_code"],
        fund_type=row["fund_type"] or "unknown",
        fund_name=row["fund_name"] or "",
        fund_size=row["fund_size"],
        manager=row["manager"] or "",
        benchmark=row["benchmark"] or "",
        strategy_keywords=keywords,
        skip_prediction=bool(row["skip_prediction"]),
        raw_info=raw_info,
        fund_type_raw=row["fund_type_raw"] or "",
        establish_date=row["establish_date"] or "",
        fee_rate=row["fee_rate"],
        strategy_text=row["strategy_text"] or "",
        risk_level=row["risk_level"] or "",
        stale=False,
        cached_at=row.get("fetched_at", ""),
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
    has_equity = bool("沪深300" in benchmark or "中证500" in benchmark or "中证800" in benchmark)
    has_bond = bool("中债" in benchmark or "国债" in benchmark or "中证全债" in benchmark)

    if has_equity and has_bond:
        equity_weight = _parse_benchmark_weight(benchmark)
        if equity_weight is not None:
            if equity_weight > 0.65:
                return "hybrid_equity"
            elif equity_weight >= 0.40:
                return "hybrid_balanced"
            else:
                return "hybrid_bond"
        return "hybrid_balanced"

    if has_equity:
        return "hybrid_equity"
    if has_bond:
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


def _risk_level_for_type(fund_type: str) -> str:
    mapping = {
        "money_market": "低风险",
        "bond_pure": "低风险",
        "bond_mixed": "中低风险",
        "bond_convertible": "中风险",
        "index_bond": "中低风险",
        "hybrid_bond": "中风险",
        "hybrid_balanced": "中高风险",
        "hybrid_flexible": "中高风险",
        "hybrid_equity": "中高风险",
        "equity_active": "高风险",
        "index_equity": "高风险",
        "fof": "中风险",
        "qdii": "高风险",
        "unknown": "未知",
    }
    return mapping.get(fund_type, "未知")
