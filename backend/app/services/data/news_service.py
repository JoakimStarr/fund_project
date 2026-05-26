import json
import hashlib
import logging
from datetime import datetime, timedelta
from sqlalchemy import select
from app.models.news_cache import NewsCache
from app.services.data.akshare_client import fetch_data, get_cls_news, get_stock_news

logger = logging.getLogger(__name__)
CACHE_MINUTES = 10


def _make_cache_key(fund_code: str) -> str:
    now = datetime.now()
    minute_block = now.strftime("%Y%m%d_%H") + str(now.minute // CACHE_MINUTES * CACHE_MINUTES)
    key = f"news:{fund_code}:{minute_block}"
    return hashlib.md5(key.encode()).hexdigest()[:16]


def _score_relevance(title: str, keywords: list[str]) -> float:
    title_lower = title.lower()
    matches = sum(1 for kw in keywords if kw.lower() in title_lower)
    if matches == 0:
        return 0.0
    return min(0.3 + matches * 0.15, 1.0)


async def fetch_relevant_news(fund_code: str, session, holdings_codes: list = None) -> list:
    cache_key = _make_cache_key(fund_code)
    result = await session.execute(select(NewsCache).where(NewsCache.cache_key == cache_key))
    cached = result.scalar_one_or_none()
    if cached:
        return json.loads(cached.news_json)
    all_news = []
    keywords = [fund_code]
    try:
        cls_df = await fetch_data(get_cls_news)
        if cls_df is not None and not cls_df.empty:
            for _, row in cls_df.head(50).iterrows():
                title = str(row.get("内容", ""))[:80]
                all_news.append({
                    "title": title,
                    "source": "财联社",
                    "source_type": "cls",
                    "published_at": str(row.get("发布时间", "")),
                    "relevance_score": _score_relevance(title, keywords),
                })
    except Exception as e:
        logger.warning(f"财联社新闻获取失败: {e}")
    if holdings_codes:
        for code in holdings_codes[:5]:
            try:
                df = await fetch_data(get_stock_news, code)
                if df is not None and not df.empty:
                    for _, row in df.head(20).iterrows():
                        title = str(row.get("新闻标题", ""))[:80]
                        all_news.append({
                            "title": title,
                            "source": "东方财富",
                            "source_type": "em",
                            "published_at": str(row.get("发布时间", "")),
                            "relevance_score": _score_relevance(title, keywords + [code]),
                        })
            except Exception as e:
                logger.warning(f"个股新闻获取失败 {code}: {e}")
    all_news.sort(key=lambda x: x["relevance_score"], reverse=True)
    session.add(NewsCache(cache_key=cache_key, news_json=json.dumps(all_news, ensure_ascii=False)))
    await session.commit()
    return all_news[:5]