"""
新闻聚合服务：通过 AKShare 从多个源拉取财经新闻，基于基金画像计算相关性得分。
支持 10 分钟缓存策略，单个源失败不影响其他源。
"""
import hashlib
import logging
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Optional

import akshare as ak

from app.core.config import (
    NEWS_SOURCES,
    NEWS_KEYWORD_SOURCES,
    NEWS_MAX_NEWS_FOR_AI,
    NEWS_MAX_NEWS_FOR_DISPLAY,
    NEWS_CACHE_MINUTES,
    NEWS_FETCH_TIMEOUT,
)
from app.core.logging_config import set_log_context
from app.db.database import get_conn

logger = logging.getLogger(__name__)


@dataclass
class NewsItem:
    """单条新闻数据结构"""
    title: str
    content: str
    source: str           # "财联社"/"东方财富"/"新浪"
    source_type: str      # "cls"/"em"/"sina"
    url: Optional[str] = None
    published_at: Optional[datetime] = None
    relevance_score: float = 0.0
    matched_keywords: list[str] = field(default_factory=list)


@dataclass
class NewsResult:
    """新闻聚合结果"""
    items: list[NewsItem]
    fetched_at: datetime
    total: int = 0
    error: Optional[str] = None


def _build_keywords_from_profile(fund_code: str) -> dict[str, list[str]]:
    """从基金画像构建关键词集合

    Args:
        fund_code: 基金代码

    Returns:
        关键词字典，包含 fund_name、top5_holdings、fund_type_keywords 三类
    """
    keywords = {
        "fund_name": [],
        "top5_holdings": [],
        "fund_type_keywords": []
    }

    try:
        from app.services.fund_profile_service import get_profile
        profile = get_profile(fund_code)

        # 基金名称关键词（去掉通用词）
        name = profile.fund_name or ""
        stop_words = {"基金", "混合", "增强", "指数", "ETF", "LOF", "型"}
        name_words = [w for w in name if w not in stop_words and len(w) > 1]
        keywords["fund_name"] = name_words[:5]

        # 基金类型关键词
        type_mapping = {
            "equity_active": ["A股", "股票", "主动管理"],
            "equity_index": ["指数", "ETF", "跟踪"],
            "bond": ["债券", "利率", "信用", "国债"],
            "mixed_equity": ["混合", "股债平衡"],
            "hybrid_flexible": ["灵活配置", "择时"],
            "money_market": ["货币", "现金管理"],
            "fof": ["FOF", "基金中基金"],
        }
        keywords["fund_type_keywords"] = type_mapping.get(profile.fund_type, [])

        # 前5大重仓股名称（需要查询持仓数据）
        if "top5_holdings" in NEWS_KEYWORD_SOURCES:
            holdings = _get_top_holdings(fund_code)
            keywords["top5_holdings"] = [h["name"] for h in holdings[:5]]

    except Exception as e:
        logger.warning("build_keywords_failed fund_code=%s error=%s", fund_code, e)

    return keywords


def _get_top_holdings(fund_code: str, limit: int = 5) -> list[dict]:
    """获取前N大重仓股信息

    Args:
        fund_code: 基金代码
        limit: 返回数量上限

    Returns:
        重仓股列表 [{"name": str, "code": str}, ...]
    """
    try:
        from app.services.holding_service import get_latest_holdings
        holdings = get_latest_holdings(fund_code)
        if holdings and len(holdings) > 0:
            return [
                {"name": h.get("stock_name", ""), "code": h.get("stock_code", "")}
                for h in holdings[:limit]
                if h.get("stock_name")
            ]
    except Exception as e:
        logger.debug("get_holdings_failed fund_code=%s error=%s", fund_code, e)

    return []


def _calculate_relevance(text: str, keywords: dict[str, list[str]]) -> tuple[float, list[str]]:
    """计算文本与关键词集合的相关性得分

    Args:
        text: 待匹配文本（title + content）
        keywords: 关键词字典

    Returns:
        (相关性得分, 匹配到的关键词列表)
    """
    if not text or not any(keywords.values()):
        return 0.0, []

    text_lower = text.lower()
    matched = []
    total_score = 0.0

    # 权重配置：重仓股 > 基金名 > 类型关键词
    weights = {
        "top5_holdings": 0.4,
        "fund_name": 0.3,
        "fund_type_keywords": 0.1,
    }

    for keyword_type, kw_list in keywords.items():
        weight = weights.get(keyword_type, 0.1)
        for kw in kw_list:
            if len(kw) < 2:
                continue
            count = text_lower.count(kw.lower())
            if count > 0:
                total_score += weight * count
                matched.append(kw)

    # 归一化到 [0, 1]
    total_keywords = sum(len(v) for v in keywords.values())
    if total_keywords > 0:
        score = min(total_score / total_keywords, 1.0)
    else:
        score = 0.0

    return score, matched


def _fetch_cls_telegraph() -> list[NewsItem]:
    """获取财联社电报

    Returns:
        新闻列表
    """
    items = []
    source_config = NEWS_SOURCES.get("cls", {})
    max_items = source_config.get("max_items", 50)

    try:
        df = ak.stock_telegraph_cls_em()
        if df is None or df.empty:
            logger.warning("cls_telegraph_empty")
            return items

        for _, row in df.head(max_items).iterrows():
            content = str(row.get("content", ""))
            time_str = str(row.get("time", ""))

            pub_time = None
            if time_str:
                try:
                    pub_time = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    pass

            items.append(NewsItem(
                title=content[:80] + ("..." if len(content) > 80 else ""),
                content=content,
                source="财联社",
                source_type="cls",
                url=None,
                published_at=pub_time,
            ))

        logger.info("cls_telegraph_fetched count=%d", len(items))

    except Exception as e:
        logger.error("cls_telegraph_fetch_error error=%s", e)

    return items


def _fetch_em_news(fund_code: str) -> list[NewsItem]:
    """获取东方财富个股/基金新闻

    Args:
        fund_code: 基金代码

    Returns:
        新闻列表
    """
    items = []
    source_config = NEWS_SOURCES.get("em", {})
    max_items = source_config.get("max_items", 20)

    try:
        df = ak.stock_news_em(symbol=fund_code)
        if df is None or df.empty:
            logger.debug("em_news_empty fund_code=%s", fund_code)
            return items

        for _, row in df.head(max_items).iterrows():
            title = str(row.get("title", ""))
            content = str(row.get("content", ""))
            url = row.get("url")
            datetime_str = str(row.get("datetime", ""))

            pub_time = None
            if datetime_str:
                try:
                    pub_time = datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
                except ValueError:
                    pass

            items.append(NewsItem(
                title=title,
                content=content,
                source="东方财富",
                source_type="em",
                url=url,
                published_at=pub_time,
            ))

        logger.info("em_news_fetched fund_code=%s count=%d", fund_code, len(items))

    except Exception as e:
        logger.warning("em_news_fetch_error fund_code=%s error=%s", fund_code, e)

    return items


def _fetch_sina_news(fund_code: str) -> list[NewsItem]:
    """获取新浪财经快讯

    Args:
        fund_code: 基金代码

    Returns:
        新闻列表
    """
    items = []
    source_config = NEWS_SOURCES.get("sina", {})
    max_items = source_config.get("max_items", 20)

    try:
        df = ak.stock_news_sina(symbol=fund_code)
        if df is None or df.empty:
            logger.debug("sina_news_empty fund_code=%s", fund_code)
            return items

        for _, row in df.head(max_items).iterrows():
            title = str(row.get("title", ""))
            url = row.get("url")
            datetime_str = str(row.get("datetime", ""))

            pub_time = None
            if datetime_str:
                try:
                    pub_time = datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
                except ValueError:
                    pass

            items.append(NewsItem(
                title=title,
                content=title,
                source="新浪",
                source_type="sina",
                url=url,
                published_at=pub_time,
            ))

        logger.info("sina_news_fetched fund_code=%s count=%d", fund_code, len(items))

    except Exception as e:
        logger.warning("sina_news_fetch_error fund_code=%s error=%s", fund_code, e)

    return items


def _filter_and_sort(news_list: list[NewsItem], keywords: dict[str, list[str]], fund_code: str) -> list[NewsItem]:
    """过滤和排序新闻列表

    Args:
        news_list: 原始新闻列表
        keywords: 关键词字典
        fund_code: 基金代码（用于日志）

    Returns:
        过滤排序后的新闻列表
    """
    now = datetime.now()
    filtered = []

    for item in news_list:
        # 计算相关性得分
        text = f"{item.title} {item.content[:300]}"
        score, matched = _calculate_relevance(text, keywords)
        item.relevance_score = score
        item.matched_keywords = matched

        # 获取该源的最低分数阈值
        source_config = NEWS_SOURCES.get(item.source_type, {})
        min_score = source_config.get("relevance_min_score", 0.3)

        # 过滤条件：达到最低阈值
        if score < min_score:
            continue

        # 过滤条件：发布时间在36小时内
        if item.published_at:
            age_hours = (now - item.published_at).total_seconds() / 3600
            if age_hours > 36:
                continue

        filtered.append(item)

    # 按相关性降序排列
    filtered.sort(key=lambda x: x.relevance_score, reverse=True)

    logger.info(
        "news_filtered fund_code=%s input=%d after_filter=%d",
        fund_code, len(news_list), len(filtered)
    )

    return filtered


def _deduplicate_by_title(news_list: list[NewsItem]) -> list[NewsItem]:
    """按标题去重（使用哈希）

    Args:
        news_list: 新闻列表

    Returns:
        去重后的列表
    """
    seen = set()
    result = []
    for item in news_list:
        title_hash = hashlib.md5(item.title.encode()).hexdigest()
        if title_hash not in seen:
            seen.add(title_hash)
            result.append(item)
    return result


def _generate_cache_key(fund_code: str) -> str:
    """生成缓存 Key

    Args:
        fund_code: 基金代码

    Returns:
        缓存键
    """
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_slot = f"{now.hour}:{now.minute // 10}"
    return f"news:{fund_code}:{date_str}:{time_slot}"


def _read_cache(cache_key: str) -> Optional[NewsResult]:
    """读取新闻缓存

    Args:
        cache_key: 缓存键

    Returns:
        缓存的 NewsResult 或 None
    """
    try:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT data, created_at FROM news_cache WHERE cache_key=? AND created_at > datetime('now', ? || ' minutes')",
                (cache_key, -NEWS_CACHE_MINUTES)
            ).fetchone()

            if row and row[0]:
                import json
                data = json.loads(row[0])
                items = [NewsItem(**item) for item in data.get("items", [])]
                return NewsResult(
                    items=items,
                    fetched_at=datetime.fromisoformat(data["fetched_at"]),
                    total=data.get("total", 0),
                )
    except Exception as e:
        logger.debug("news_cache_read_error key=%s error=%s", cache_key, e)

    return None


def _write_cache(cache_key: str, result: NewsResult) -> None:
    """写入新闻缓存

    Args:
        cache_key: 缓存键
        result: 新闻结果
    """
    try:
        import json
        data = {
            "items": [asdict(item) for item in result.items],
            "fetched_at": result.fetched_at.isoformat(),
            "total": result.total,
        }

        with get_conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO news_cache (cache_key, data, created_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (cache_key, json.dumps(data, ensure_ascii=False)))
            conn.commit()

        logger.info("news_cache_written key=%s items=%d", cache_key, len(result.items))
    except Exception as e:
        logger.warning("news_cache_write_error key=%s error=%s", cache_key, e)


def _ensure_cache_table() -> None:
    """确保 news_cache 表存在"""
    try:
        with get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS news_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cache_key TEXT NOT NULL UNIQUE,
                    data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
    except Exception as e:
        logger.error("news_cache_table_init_error error=%s", e)


async def fetch_relevant_news(fund_code: str, limit: int = 5) -> NewsResult:
    """获取与基金相关的新闻列表（主入口函数）

    并发调用多个新闻源，基于基金画像计算相关性，返回最相关的新闻。

    Args:
        fund_code: 基金代码
        limit: 返回的最大条数（最多10）

    Returns:
        NewsResult 对象
    """
    set_log_context(fund_code=fund_code)
    limit = min(max(limit, 1), 10)

    # 确保缓存表存在
    _ensure_cache_table()

    # 检查缓存
    cache_key = _generate_cache_key(fund_code)
    cached = _read_cache(cache_key)
    if cached:
        cached.items = cached.items[:limit]
        cached.total = len(cached.items)
        logger.info("news_cache_hit fund_code=%s items=%d", fund_code, len(cached.items))
        return cached

    # 构建关键词
    keywords = _build_keywords_from_profile(fund_code)

    # 并发获取各源新闻
    all_news = []
    sources_to_fetch = []

    for source_id, config in NEWS_SOURCES.items():
        if not config.get("enabled", False):
            continue
        sources_to_fetch.append(source_id)

    import asyncio

    async def fetch_source(source_id: str) -> list[NewsItem]:
        loop = asyncio.get_event_loop()
        if source_id == "cls":
            return await loop.run_in_executor(None, _fetch_cls_telegraph)
        elif source_id == "em":
            return await loop.run_in_executor(None, _fetch_em_news, fund_code)
        elif source_id == "sina":
            return await loop.run_in_executor(None, _fetch_sina_news, fund_code)
        return []

    tasks = [fetch_source(s) for s in sources_to_fetch]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for i, result in enumerate(results):
        source_id = sources_to_fetch[i]
        if isinstance(result, Exception):
            logger.warning(
                "news_source_error source=%s error=%s", source_id, result
            )
            continue
        all_news.extend(result)

    # 去重
    all_news = _deduplicate_by_title(all_news)

    # 过滤和排序
    filtered = _filter_and_sort(all_news, keywords, fund_code)

    # 截断到指定数量
    display_items = filtered[:limit]

    result = NewsResult(
        items=display_items,
        fetched_at=datetime.now(),
        total=len(filtered),
    )

    # 写入缓存
    _write_cache(cache_key, result)

    logger.info(
        "news_fetched fund_code=%s total_sources=%d total_raw=%d "
        "after_dedup=%d after_filter=%d returned=%d",
        fund_code, len(sources_to_fetch), len(all_news),
        len(_deduplicate_by_title(all_news)), len(filtered), len(display_items)
    )

    return result
