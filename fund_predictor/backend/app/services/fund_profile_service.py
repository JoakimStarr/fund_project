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
    # 新增字段：资产配置和行业分布
    asset_allocation: dict = field(default_factory=dict)  # {"股票": 60, "债券": 25, ...}
    industry_distribution: list = field(default_factory=list)  # [{"name": "科技", "value": 30}, ...]


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
    logger.info("Fetching profile for fund: %s", fund_code)

    info = _fetch_from_primary_source(fund_code)
    if info is None:
        logger.warning("All data sources failed for fund %s, returning minimal profile", fund_code)
        return _get_minimal_profile(fund_code)

    logger.debug("AKShare returned info keys: %s", list(info.keys()) if info else "None")

    # 字段提取：支持多种可能的字段名（兼容不同数据源）
    def _get_field(info_dict, *possible_keys, default=""):
        """尝试从字典中获取字段值，支持多个候选键名"""
        for key in possible_keys:
            val = info_dict.get(key)
            if val is not None and str(val).strip():
                return str(val).strip()
        return default

    raw_type = _get_field(info, "基金类型", "基金类型（新）", "type", "fund_type")
    benchmark = _get_field(info, "业绩比较基准", "比较基准", "benchmark")
    strategy = _get_field(info, "投资策略", "投资目标", "strategy")
    fund_name = _get_field(info, "基金名称", "基金简称", "NAME", "name", "SHORTNAME")  # 优先"基金名称"
    establish_date = _get_field(info, "成立日期", "成立时间", "SETUPDATE", "setupDate", "establish_date")
    size = _parse_size(_get_field(info, "最新规模", "基金规模", "资产规模", "SCALE", "scale"))
    manager = _get_field(info, "基金经理", "经理", "MANAGER", "manager")
    fee_rate = _extract_fee_rate(info)
    keywords = _extract_strategy_keywords(strategy)

    fund_type = _classify_by_type(raw_type)
    if fund_type == "unknown":
        fund_type = _classify_by_benchmark(benchmark)

    skip = (fund_type == "money_market")

    risk_level = _classify_risk_level_from_info(info, fund_type)

    # 获取管理费率（如果基础信息中没有，尝试详细接口）
    if fee_rate is None:
        fee_rate = _extract_fee_rate_from_detail(fund_code)
    
    # 获取资产配置和行业分布
    logger.info("Fetching asset allocation and industry distribution for %s", fund_code)
    asset_allocation = _get_asset_allocation(fund_code)
    industry_distribution = _get_industry_distribution(fund_code)
    
    logger.info(
        "fund_classified fund_code=%s type=%s name=%s establish_date=%s size=%s manager=%s fee_rate=%s "
        "asset_allocation=%s industry_count=%d",
        fund_code, fund_type, fund_name, establish_date or "(empty)", size, manager or "(empty)", fee_rate,
        bool(asset_allocation), len(industry_distribution)
    )

    return FundProfile(
        fund_code=fund_code,
        fund_type=fund_type,
        fund_name=fund_name or "暂无数据",
        fund_size=size,
        manager=manager or "暂无数据",
        benchmark=benchmark or "暂无数据",
        strategy_keywords=keywords,
        skip_prediction=skip,
        raw_info=info,
        fund_type_raw=raw_type,
        establish_date=establish_date or "-",
        fee_rate=fee_rate,
        strategy_text=strategy,
        risk_level=risk_level,
        asset_allocation=asset_allocation,
        industry_distribution=industry_distribution,
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
                    data_source, fetched_at, updated_at, cache_ttl_days, raw_info_json,
                    asset_allocation_json, industry_distribution_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'akshare', ?, ?, 7, ?, ?, ?)
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
                    raw_info_json=excluded.raw_info_json,
                    asset_allocation_json=excluded.asset_allocation_json,
                    industry_distribution_json=excluded.industry_distribution_json
                """,
                [
                    profile.fund_code, profile.fund_name, profile.fund_type, profile.fund_type_raw,
                    profile.establish_date, profile.fund_size, profile.manager, profile.fee_rate,
                    profile.benchmark, profile.strategy_text,
                    json.dumps(profile.strategy_keywords, ensure_ascii=False),
                    int(profile.skip_prediction), profile.risk_level,
                    now, now,
                    json.dumps(profile.raw_info, ensure_ascii=False, default=str),
                    json.dumps(profile.asset_allocation, ensure_ascii=False),
                    json.dumps(profile.industry_distribution, ensure_ascii=False),
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
    
    # 解析资产配置
    alloc_str = row.get("asset_allocation_json") or "{}"
    try:
        asset_allocation = json.loads(alloc_str)
    except Exception:
        asset_allocation = {}
    
    # 解析行业分布
    industry_str = row.get("industry_distribution_json") or "[]"
    try:
        industry_distribution = json.loads(industry_str)
    except Exception:
        industry_distribution = []
    
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
        asset_allocation=asset_allocation,
        industry_distribution=industry_distribution,
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


def _fetch_from_primary_source(fund_code: str) -> Optional[dict]:
    import akshare as ak
    import pandas as pd

    try:
        info = ak.fund_individual_basic_info_xq(symbol=fund_code)

        # 转换 DataFrame 为字典（AKShare 返回格式：[['item', 'value'], ...]）
        if info is not None:
            if isinstance(info, pd.DataFrame) and not info.empty:
                # 将 item-value 格式的 DataFrame 转为普通字典
                if 'item' in info.columns and 'value' in info.columns:
                    result_dict = {}
                    for _, row in info.iterrows():
                        key = str(row['item']).strip()
                        val = row['value']
                        # 处理 NaN 值
                        if pd.isna(val) or (isinstance(val, float) and (val != val)):  # NaN check
                            result_dict[key] = ''
                        else:
                            result_dict[key] = str(val).strip() if val is not None else ''
                    logger.info(
                        "Primary source (xueqiu) succeeded for fund %s, got %d fields",
                        fund_code, len(result_dict)
                    )
                    return result_dict
                # 其他格式的 DataFrame，转为字典记录
                elif isinstance(info, pd.DataFrame):
                    logger.warning("Primary source returned unexpected DataFrame format for fund %s", fund_code)
                    return None
            elif isinstance(info, dict) and len(info) > 0:
                logger.info("Primary source (xueqiu) succeeded for fund %s (dict format)", fund_code)
                return {str(k): str(v) for k, v in info.items()}

        logger.warning("Primary source returned empty/invalid data for fund %s", fund_code)
    except Exception as exc:
        logger.warning("Primary source (xueqiu) failed for %s: %s", fund_code, exc)

    try:
        logger.info("Trying fallback source (eastmoney) for fund %s", fund_code)
        info = ak.fund_individual_basic_info_em(symbol=fund_code)

        # 同样处理 eastmoney 可能返回的 DataFrame
        if info is not None:
            if isinstance(info, pd.DataFrame) and not info.empty:
                if 'item' in info.columns and 'value' in info.columns:
                    result_dict = {}
                    for _, row in info.iterrows():
                        key = str(row['item']).strip()
                        val = row['value']
                        if pd.isna(val) or (isinstance(val, float) and (val != val)):
                            result_dict[key] = ''
                        else:
                            result_dict[key] = str(val).strip() if val is not None else ''
                    logger.info("Fallback source (eastmoney) succeeded for fund %s", fund_code)
                    return _normalize_eastmoney_info(result_dict)
            elif isinstance(info, dict) and len(info) > 0:
                logger.info("Fallback source (eastmoney) succeeded for fund %s (dict format)", fund_code)
                return _normalize_eastmoney_info(info)

        logger.warning("Fallback source returned empty data for fund %s", fund_code)
    except Exception as exc:
        logger.warning("Fallback source (eastmoney) failed for %s: %s", fund_code, exc)

    return None


def _normalize_eastmoney_info(info: dict) -> dict:
    field_map = {
        "基金简称": ["基金简称", "基金名称", "NAME", "name", "SHORTNAME"],
        "基金类型": ["基金类型", "TYPE", "type", "FUNDTYPE"],
        "成立日期": ["成立日期", "成立时间", "SETUPDATE", "setupDate"],
        "最新规模": ["最新规模", "基金规模", "资产规模", "SCALE", "scale"],
        "基金经理": ["基金经理", "经理", "MANAGER", "manager"],
        "业绩比较基准": ["业绩比较基准", "比较基准", "BENCHMARK", "benchmark"],
        "投资策略": ["投资策略", "投资目标", "策略", "INVESTRATEGY"],
    }
    result = {}
    for target_key, source_keys in field_map.items():
        for sk in source_keys:
            val = info.get(sk)
            if val is not None and str(val).strip():
                result[target_key] = val
                break
        if target_key not in result:
            result[target_key] = info.get(target_key, "")
    return result


def _extract_fee_rate(info: dict) -> Optional[float]:
    fee_fields = [
        ("管理费率", r"([\d.]+)%?"),
        ("托管费率", r"([\d.]+)%?"),
        ("销售服务费率", r"([\d.]+)%?"),
    ]
    total_fee = 0.0
    found = False
    import re
    for field_name, pattern in fee_fields:
        raw = info.get(field_name, "")
        if not raw:
            continue
        match = re.search(pattern, str(raw))
        if match:
            try:
                total_fee += float(match.group(1))
                found = True
            except ValueError:
                continue
    return round(total_fee, 2) if found else None


def _classify_risk_level_from_info(info: dict, fund_type: str) -> str:
    risk_from_info = str(info.get("风险等级", "") or "").strip()
    if risk_from_info and risk_from_info != "-" and risk_from_info != "未知":
        return risk_from_info
    return _risk_level_for_type(fund_type)


def _extract_fee_rate_from_detail(fund_code: str) -> Optional[float]:
    """从基金详情页面获取管理费率（更详细的接口）"""
    import akshare as ak
    try:
        # 尝试使用东方财富的详细接口
        info = ak.fund_individual_detail_info_xq(symbol=fund_code)
        if info is not None and not info.empty:
            # 转换为字典
            if 'item' in info.columns and 'value' in info.columns:
                detail_dict = {}
                for _, row in info.iterrows():
                    key = str(row['item']).strip()
                    val = row['value']
                    if not pd.isna(val):
                        detail_dict[key] = str(val).strip()
                
                # 查找费率信息
                fee_str = detail_dict.get('管理费率', '') or detail_dict.get('费率', '')
                if fee_str:
                    import re
                    match = re.search(r'([\d.]+)%?', fee_str)
                    if match:
                        return round(float(match.group(1)), 2)
    except Exception as e:
        logger.debug("Detail info fetch failed for %s: %s", fund_code, e)
    
    return None


def _get_asset_allocation(fund_code: str) -> dict:
    """获取基金资产配置（股票、债券、现金等占比）"""
    import akshare as ak
    import pandas as pd
    
    try:
        # 使用基金公开信息中的资产配置数据
        # 尝试从基金详情页面获取
        info = ak.fund_individual_detail_info_xq(symbol=fund_code)
        if info is not None and not info.empty:
            detail_dict = {}
            if 'item' in info.columns and 'value' in info.columns:
                for _, row in info.iterrows():
                    key = str(row['item']).strip()
                    val = row['value']
                    if not pd.isna(val):
                        detail_dict[key] = str(val).strip()
            
            # 尝试解析资产配置字段
            allocation = {}
            
            # 查找股票、债券、现金等占比
            asset_fields = {
                '股票占净值比例': '股票',
                '债券占净值比例': '债券',
                '现金占净值比例': '现金',
                '基金占净值比例': '基金',
                '其他资产占净值比例': '其他',
                '银行存款占净值比例': '银行存款',
                '买入返售金融资产占净值比例': '买入返售',
                '资产分布-股票': '股票',
                '资产分布-债券': '债券',
                '资产分布-现金': '现金',
            }
            
            for field_key, alloc_name in asset_fields.items():
                if field_key in detail_dict:
                    try:
                        val_str = detail_dict[field_key]
                        # 提取数字（可能包含 % 符号）
                        import re
                        match = re.search(r'([\d.]+)', val_str.replace('%', ''))
                        if match:
                            value = float(match.group(1))
                            if value > 0:
                                allocation[alloc_name] = round(value, 2)
                    except (ValueError, TypeError):
                        continue
            
            if allocation:
                logger.info("Asset allocation fetched for %s: %s", fund_code, allocation)
                return allocation
                
    except Exception as e:
        logger.debug("Asset allocation from detail failed for %s: %s", fund_code, e)
    
    # 备选：从持仓数据计算近似资产配置
    try:
        return _calculate_asset_from_holdings(fund_code)
    except Exception as e:
        logger.debug("Asset from holdings failed for %s: %s", fund_code, e)
    
    return {}


def _get_industry_distribution(fund_code: str) -> list:
    """获取基金行业分布（前N大行业占比）"""
    import akshare as ak
    import pandas as pd
    
    try:
        # 使用 cninfo 的行业配置报告
        df = ak.fund_report_industry_allocation_cninfo(symbol=fund_code)
        if df is not None and not df.empty:
            # 获取最新报告期
            latest_period = df.iloc[0].get('报告期', '')
            latest_data = df[df['报告期'] == latest_period] if latest_period else df
            
            industries = []
            for _, row in latest_data.iterrows():
                try:
                    name = row.get('行业名称', row.get('行业', ''))
                    ratio = float(row.get('占净值比例', row.get('比例', 0)))
                    if name and ratio > 0:
                        industries.append({
                            'name': str(name),
                            'value': round(ratio, 2)
                        })
                except (ValueError, TypeError):
                    continue
            
            # 按占比排序，取前10
            industries = sorted(industries, key=lambda x: x['value'], reverse=True)[:10]
            
            if industries:
                logger.info("Industry distribution fetched for %s: %d industries", 
                          fund_code, len(industries))
                return industries
                
    except Exception as e:
        logger.warning("Industry distribution fetch failed for %s: %s", fund_code, e)
    
    # 备选方案：从持仓数据计算行业分布
    try:
        return _calculate_industry_from_holdings(fund_code)
    except Exception as e:
        logger.debug("Industry from holdings failed for %s: %s", fund_code, e)
    
    return []


def _calculate_asset_from_holdings(fund_code: str) -> dict:
    """从持仓数据计算近似资产配置"""
    import akshare as ak
    
    try:
        df = ak.fund_portfolio_hold_em(symbol=fund_code, date="2024")
        if df is None or df.empty:
            return {}
        
        # 获取最新季度
        latest_quarter = df.iloc[0].get('季度', '')
        latest_df = df[df['季度'] == latest_quarter] if latest_quarter else df
        
        # 计算股票持仓占比（前10大持仓之和作为近似）
        stock_ratio = 0
        for _, row in latest_df.iterrows():
            try:
                ratio = float(row.get('占净值比例', 0))
                stock_ratio += ratio
            except (ValueError, TypeError):
                continue
        
        # 简化假设：剩余部分为现金+债券
        if stock_ratio > 0:
            return {
                '股票': round(stock_ratio, 2),
                '债券': round(max(0, 80 - stock_ratio), 2),  # 假设债券约20-30%
                '现金': round(max(0, 20 - (80 - stock_ratio)), 2)  # 剩余为现金
            }
        
    except Exception as e:
        logger.debug("Asset calculation from holdings failed for %s: %s", fund_code, e)
    
    return {}


def _calculate_industry_from_holdings(fund_code: str) -> list:
    """从持仓数据计算行业分布（备选方案）"""
    import akshare as ak
    
    try:
        # 获取最新持仓
        df = ak.fund_portfolio_hold_em(symbol=fund_code, date="2024")
        if df is None or df.empty:
            return []
        
        # 获取最新季度
        latest_quarter = df.iloc[0].get('季度', '')
        latest_df = df[df['季度'] == latest_quarter] if latest_quarter else df
        
        # 获取股票代码列表
        stock_codes = latest_df['股票代码'].tolist()
        
        # 获取每个股票的行业（这里简化处理，实际可以查询股票行业）
        # 返回持仓占比作为近似
        industries = []
        for _, row in latest_df.head(10).iterrows():  # 取前10大持仓
            try:
                name = row.get('股票名称', '')
                ratio = float(row.get('占净值比例', 0))
                if name and ratio > 0:
                    industries.append({
                        'name': str(name),  # 用股票名代替行业名（简化）
                        'value': round(ratio, 2)
                    })
            except (ValueError, TypeError):
                continue
        
        return industries
        
    except Exception as e:
        logger.debug("Holdings calculation failed for %s: %s", fund_code, e)
        return []


def _get_minimal_profile(fund_code: str) -> FundProfile:
    return FundProfile(
        fund_code=fund_code,
        fund_type="unknown",
        fund_name="暂无数据",
        establish_date="-",
        fund_size=None,
        manager="暂无数据",
        fee_rate=None,
        benchmark="暂无数据",
        risk_level="未知",
        strategy_text="数据获取失败，请稍后重试",
        skip_prediction=True,
    )
