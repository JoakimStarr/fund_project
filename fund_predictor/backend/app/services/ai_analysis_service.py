"""
AI 分析服务：Provider 路由、Prompt 组装、AI 调用、输出解析与缓存
支持主 Provider → 备用 Provider 自动切换，当日缓存管理
"""
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from typing import Optional, Any

from app.core.config import (
    AI_ENABLED,
    AI_PRIMARY_PROVIDER,
    AI_PRIMARY_API_KEY,
    AI_PRIMARY_BASE_URL,
    AI_PRIMARY_MODEL,
    AI_PRIMARY_TIMEOUT,
    AI_PRIMARY_MAX_TOKENS,
    AI_PRIMARY_TEMPERATURE,
    AI_FALLBACK_PROVIDER,
    AI_FALLBACK_API_KEY,
    AI_FALLBACK_BASE_URL,
    AI_FALLBACK_MODEL,
    AI_FALLBACK_TIMEOUT,
    AI_FALLBACK_MAX_TOKENS,
    AI_FALLBACK_TEMPERATURE,
    AI_RETRY_TIMES,
    AI_RETRY_DELAY,
    AI_FALLBACK_ON_ERROR,
    AI_ALLOWED_ACTIONS,
)
from app.core.errors import AIProviderError
from app.core.logging_config import set_log_context
from app.db.database import get_conn

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    """LLM 客户端配置"""
    provider: str
    api_key: str
    base_url: str
    model: str
    timeout: int
    max_tokens: int
    temperature: float


@dataclass
class ProviderStatus:
    """Provider 状态信息"""
    provider: str
    model: str
    status: str  # "available" / "unavailable" / "unknown"
    latency_ms: Optional[int] = None
    last_checked: Optional[datetime] = None
    error: Optional[str] = None


class LLMClient:
    """统一 LLM 客户端（支持智谱 zai 库和 OpenAI 兼容格式）"""

    def __init__(self, config: LLMConfig):
        self.config = config
        self._client = None

    def _get_client(self):
        """获取或创建 LLM 客户端实例
        
        根据 provider 类型选择合适的客户端：
        - glm: 使用 ZhipuAiClient (zai 库)
        - 其他: 使用 httpx (OpenAI 兼容格式)
        """
        if self._client is not None:
            return self._client
            
        if self.config.provider == "glm":
            # 使用智谱官方 zai 库
            try:
                from zai import ZhipuAiClient
                
                self._client = ZhipuAiClient(
                    api_key=self.config.api_key,
                    base_url=self.config.base_url
                )
                
                logger.info(
                    "zai_client_created provider=%s model=%s base_url=%s",
                    self.config.provider, 
                    self.config.model,
                    self.config.base_url
                )
                return self._client
                
            except ImportError as e:
                logger.error("zai_library_not_installed error=%s", e)
                raise AIProviderError(
                    "zai 库未安装，请运行: pip install zai",
                    provider=self.config.provider,
                    details={"error": str(e)}
                )
        else:
            # 使用 httpx (OpenAI 兼容格式，用于 SiliconFlow 等)
            import httpx
            
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.config.timeout, connect=10.0),
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                },
            )
            
            logger.info(
                "httpx_client_created provider=%s model=%s base_url=%s",
                self.config.provider,
                self.config.model,
                self.config.base_url
            )
            return self._client

    async def chat(self, prompt: str) -> str:
        """发送 Chat Completion 请求

        Args:
            prompt: 用户 Prompt

        Returns:
            AI 响应文本

        Raises:
            AIProviderError: 请求失败时抛出
        """
        client = self._get_client()
        
        if self.config.provider == "glm":
            # 使用 zai 库调用智谱 API
            return await self._chat_with_zai(client, prompt)
        else:
            # 使用 httpx 调用 OpenAI 兼容 API
            return await self._chat_with_httpx(client, prompt)

    async def _chat_with_zai(self, client, prompt: str) -> str:
        """使用 zai 库调用智谱 GLM API"""
        
        for attempt in range(AI_RETRY_TIMES + 1):
            try:
                logger.debug(
                    "llm_request_zai provider=%s model=%s attempt=%d",
                    self.config.provider, self.config.model, attempt + 1
                )

                # zai 库的 chat.completions.create 是同步方法，需要在线程池中运行
                import asyncio
                
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: client.chat.completions.create(
                        model=self.config.model,
                        messages=[
                            {"role": "user", "content": prompt}
                        ],
                        temperature=self.config.temperature,
                        max_tokens=self.config.max_tokens,
                    )
                )
                
                result_text = response.choices[0].message.content
                
                logger.info(
                    "llm_success_zai provider=%s model=%s tokens_used=%s",
                    self.config.provider,
                    self.config.model,
                    response.usage.total_tokens if hasattr(response, 'usage') else 'unknown',
                )
                
                return result_text

            except Exception as e:
                logger.warning(
                    "llm_error_zai provider=%s attempt=%d error=%s",
                    self.config.provider, attempt + 1, str(e)
                )
                
                if attempt < AI_RETRY_TIMES:
                    import asyncio
                    await asyncio.sleep(AI_RETRY_DELAY * (attempt + 1))
                    continue
                    
                raise AIProviderError(
                    f"智谱 API 调用失败 ({self.config.provider})",
                    provider=self.config.provider,
                    details={"error": str(e), "attempt": attempt + 1}
                )

    async def _chat_with_httpx(self, client, prompt: str) -> str:
        """使用 httpx 调用 OpenAI 兼容 API (SiliconFlow 等)"""
        
        url = f"{self.config.base_url.rstrip('/')}/chat/completions"
        
        payload = {
            "model": self.config.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }

        for attempt in range(AI_RETRY_TIMES + 1):
            try:
                logger.debug(
                    "llm_request_httpx provider=%s model=%s attempt=%d",
                    self.config.provider, self.config.model, attempt + 1
                )

                response = await client.post(url, json=payload)
                response.raise_for_status()

                data = response.json()
                result_text = data["choices"][0]["message"]["content"]

                logger.info(
                    "llm_success_httpx provider=%s model=%s tokens_used=%s",
                    self.config.provider,
                    self.config.model,
                    data.get("usage", {}).get("total_tokens", "unknown"),
                )

                return result_text

            except Exception as e:
                logger.warning(
                    "llm_error_httpx provider=%s attempt=%d error=%s",
                    self.config.provider, attempt + 1, str(e)
                )
                
                if attempt < AI_RETRY_TIMES:
                    import asyncio
                    await asyncio.sleep(AI_RETRY_DELAY * (attempt + 1))
                    continue
                    
                raise AIProviderError(
                    f"API 调用失败 ({self.config.provider})",
                    provider=self.config.provider,
                    details={"error": str(e), "attempt": attempt + 1}
                )

            except httpx.ReadTimeout as e:
                logger.warning(
                    "llm_timeout provider=%s timeout=%ds",
                    self.config.provider, self.config.timeout
                )
                if attempt < AI_RETRY_TIMES:
                    continue
                raise AIProviderError(
                    f"请求超时 ({self.config.provider})",
                    provider=self.config.provider,
                    details={"timeout": self.config.timeout}
                )

            except Exception as e:
                logger.error(
                    "llm_unknown_error provider=%s error=%s",
                    self.config.provider, e
                )
                raise AIProviderError(
                    f"未知错误 ({self.config.provider}): {e}",
                    provider=self.config.provider,
                    details={"error": str(e)}
                )

        raise AIProviderError(
            f"重试耗尽 ({self.config.provider})",
            provider=self.config.provider
        )

    async def health_check(self) -> ProviderStatus:
        """检测 Provider 可用性

        Returns:
            ProviderStatus 对象
        """
        start_time = datetime.now()
        try:
            test_response = await self.chat("ping")
            latency_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            return ProviderStatus(
                provider=self.config.provider,
                model=self.config.model,
                status="available" if test_response else "unknown",
                latency_ms=latency_ms,
                last_checked=datetime.now(),
            )

        except AIProviderError as e:
            return ProviderStatus(
                provider=self.config.provider,
                model=self.config.model,
                status="unavailable",
                last_checked=datetime.now(),
                error=str(e),
            )
        except Exception as e:
            return ProviderStatus(
                provider=self.config.provider,
                model=self.config.model,
                status="unknown",
                last_checked=datetime.now(),
                error=str(e),
            )

    async def close(self):
        """关闭 HTTP 客户端"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()


def _create_primary_client() -> Optional[LLMClient]:
    """创建主 Provider 客户端

    Returns:
        LLMClient 实例或 None（未配置时）
    """
    if not AI_PRIMARY_API_KEY:
        logger.warning("primary_provider_no_api_key")
        return None

    config = LLMConfig(
        provider=AI_PRIMARY_PROVIDER,
        api_key=AI_PRIMARY_API_KEY,
        base_url=AI_PRIMARY_BASE_URL,
        model=AI_PRIMARY_MODEL,
        timeout=AI_PRIMARY_TIMEOUT,
        max_tokens=AI_PRIMARY_MAX_TOKENS,
        temperature=AI_PRIMARY_TEMPERATURE,
    )
    return LLMClient(config)


def _create_fallback_client() -> Optional[LLMClient]:
    """创建备用 Provider 客户端

    Returns:
        LLMClient 实例或 None（未配置时）
    """
    if not AI_FALLBACK_API_KEY:
        logger.warning("fallback_provider_no_api_key")
        return None

    config = LLMConfig(
        provider=AI_FALLBACK_PROVIDER,
        api_key=AI_FALLBACK_API_KEY,
        base_url=AI_FALLBACK_BASE_URL,
        model=AI_FALLBACK_MODEL,
        timeout=AI_FALLBACK_TIMEOUT,
        max_tokens=AI_FALLBACK_MAX_TOKENS,
        temperature=AI_FALLBACK_TEMPERATURE,
    )
    return LLMClient(config)


def _ensure_cache_table() -> None:
    """确保 ai_analysis_cache 表存在"""
    try:
        with get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ai_analysis_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fund_code TEXT NOT NULL,
                    trade_date TEXT NOT NULL,
                    source TEXT NOT NULL,
                    analysis_json TEXT NOT NULL,
                    provider_used TEXT,
                    model_used TEXT,
                    news_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(fund_code, trade_date, source)
                )
            """)
            conn.commit()
    except Exception as e:
        logger.error("ai_cache_table_init_error error=%s", e)


def _read_ai_cache(fund_code: str, source: str) -> Optional[dict]:
    """读取 AI 分析缓存

    Args:
        fund_code: 基金代码
        source: 来源类型 ("intraday"/"predict")

    Returns:
        缓存的分析结果字典或 None
    """
    today = date.today().isoformat()

    try:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT analysis_json, provider_used, model_used, news_count, created_at "
                "FROM ai_analysis_cache WHERE fund_code=? AND trade_date=? AND source=?",
                (fund_code, today, source)
            ).fetchone()

            if row and row[0]:
                return {
                    "analysis": json.loads(row[0]),
                    "provider_used": row[1],
                    "model_used": row[2],
                    "news_count": row[3],
                    "created_at": row[4],
                }
    except Exception as e:
        logger.debug("ai_cache_read_error fund_code=%s error=%s", fund_code, e)

    return None


def _write_ai_cache(
    fund_code: str,
    source: str,
    analysis: dict,
    provider_used: str,
    model_used: str,
    news_count: int = 0,
) -> None:
    """写入 AI 分析缓存

    Args:
        fund_code: 基金代码
        source: 来源类型
        analysis: 分析结果字典
        provider使用的 Provider 名称
        model使用的模型名称
        news_count: 使用的新闻条数
    """
    today = date.today().isoformat()

    try:
        with get_conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO ai_analysis_cache
                (fund_code, trade_date, source, analysis_json, provider_used, model_used, news_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                fund_code, today, source,
                json.dumps(analysis, ensure_ascii=False),
                provider_used, model_used, news_count
            ))
            conn.commit()

        logger.info(
            "ai_cache_written fund_code=%s source=%s provider=%s model=%s",
            fund_code, source, provider_used, model_used
        )
    except Exception as e:
        logger.warning("ai_cache_write_error fund_code=%s error=%s", fund_code, e)


def _build_holdings_freshness_note(fund_code: str) -> str:
    """构建持仓时效说明

    Args:
        fund_code: 基金代码

    Returns:
        时效说明字符串
    """
    try:
        from app.services.holding_service import get_latest_holdings
        holdings = get_latest_holdings(fund_code)

        if not holdings:
            return ""

        report_date_str = holdings[0].get("report_date", "")
        if not report_date_str:
            return ""

        try:
            report_date = datetime.strptime(report_date_str, "%Y-%m-%d").date()
        except ValueError:
            return ""

        days_since = (date.today() - report_date).days
        quarter = f"{report_date.year}Q{(report_date.month - 1) // 3 + 1}"

        if days_since <= 30:
            return f"（数据较新：{quarter}季报，距今{days_since}天，准确性高）"
        elif days_since <= 60:
            return f"（数据适中：{quarter}季报，距今{days_since}天，可能存在调仓）"
        else:
            return f"（数据较旧：{quarter}季报，距今{days_since}天，实际持仓可能有较大变化，分析仅供参考）"

    except Exception as e:
        logger.debug("holdings_freshness_error fund_code=%s error=%s", fund_code, e)
        return ""


def _build_extra_info(fund_code: str, fund_type: str) -> dict[str, Any]:
    """构建基金特定信息（用于 Prompt 模板）

    Args:
        fund_code: 基金代码
        fund_type: 基金类型

    Returns:
        额外信息字典
    """
    extra = {}

    try:
        # 获取重仓股信息
        from app.services.holding_service import get_latest_holdings
        holdings = get_latest_holdings(fund_code)

        if holdings:
            top10_lines = []
            for i, h in enumerate(holdings[:10], 1):
                name = h.get("stock_name", "")
                weight = h.get("weight", "")
                top10_lines.append(f"{i}. {name} ({weight})")

            extra["top10_holdings_list"] = "\n".join(top10_lines) if top10_lines else "暂无"

            # 获取实时行情（如果可用）
            try:
                from app.services.stock_price_service import StockPriceService
                stock_service = StockPriceService()

                realtime_lines = []
                for h in holdings[:5]:
                    code = h.get("stock_code", "")
                    name = h.get("stock_name", "")
                    if code:
                        price_info = stock_service.get_realtime_price(code)
                        if price_info:
                            change_pct = price_info.get("change_percent", 0)
                            realtime_lines.append(f"{name}: {change_pct:+.2f}%")

                extra["holdings_realtime_summary"] = "\n".join(realtime_lines) if realtime_lines else "暂无实时行情"
            except Exception as e:
                logger.debug("realtime_quote_error fund_code=%s error=%s", fund_code, e)
                extra["holdings_realtime_summary"] = "暂无实时行情"

        # 根据基金类型添加特定信息
        if fund_type in ("equity_active", "equity_index"):
            extra.setdefault("sector_exposure", "待分析")
            extra.setdefault("style_label", "待分析")

        elif fund_type == "bond":
            extra.setdefault("duration", "未知")
            extra.setdefault("bond_subtype_display", "纯债基金")
            extra.setdefault("cn10y_change", "N/A")
            extra.setdefault("term_spread", "N/A")
            extra.setdefault("term_spread_change", "N/A")
            extra.setdefault("dr007", "N/A")
            extra.setdefault("credit_spread_aaa", "N/A")

        elif fund_type == "mixed_equity" or fund_type == "hybrid_flexible":
            extra.setdefault("estimated_equity_position", "未知")
            extra.setdefault("estimated_bond_position", "未知")
            extra.setdefault("hs300_return", "N/A")
            extra.setdefault("cn10y_change", "N/A")

        elif fund_type.startswith("index"):
            extra.setdefault("target_index_name", "未知")
            extra.setdefault("target_index_code", "")
            extra.setdefault("target_index_return", 0)
            extra.setdefault("tracking_error_bp", "N/A")

    except Exception as e:
        logger.warning("build_extra_info_error fund_code=%s error=%s", fund_code, e)

    return extra


async def get_analysis(
    fund_code: str,
    estimation_return: float,
    lower_bound: float,
    upper_bound: float,
    source: str = "intraday",
    refresh: bool = False,
) -> dict:
    """获取 AI 分析结果（主入口函数）

    Args:
        fund_code: 基金代码
        estimation_return: 当前估算/预测收益率
        lower_bound: 置信区间下界
        upper_bound: 置信区间上界
        source: 分析来源 ("intraday"/"predict")
        refresh: 是否强制刷新缓存

    Returns:
        包含 analysis、news_used 等的完整结果字典
    """
    set_log_context(fund_code=fund_code, stage="ai_analysis")

    if not AI_ENABLED:
        raise AIProviderError(
            "AI分析功能未启用，请联系管理员配置API Key",
            provider="none"
        )

    _ensure_cache_table()

    # 检查缓存
    if not refresh:
        cached = _read_ai_cache(fund_code, source)
        if cached:
            cached["cached"] = True
            logger.info("ai_cache_hit fund_code=%s source=%s", fund_code, source)
            return cached

    # 并发获取新闻和持仓信息
    import asyncio
    from app.services.news_service import fetch_relevant_news
    from app.services.fund_profile_service import get_profile

    profile = get_profile(fund_code)

    async def fetch_news_task():
        return await fetch_relevant_news(fund_code, limit=NEWS_MAX_NEWS_FOR_AI)

    news_result = await fetch_news_task()

    # 构建新闻列表（用于 Prompt）
    news_items_for_prompt = [
        {
            "title": item.title,
            "source": item.source,
            "relevance_score": item.relevance_score,
        }
        for item in news_result.items[:NEWS_MAX_NEWS_FOR_AI]
    ]

    # 构建新闻列表（用于返回前端）
    news_items_for_display = [
        {
            "title": item.title,
            "content": item.content[:200] if item.content else "",
            "source": item.source,
            "source_type": item.source_type,
            "url": item.url,
            "published_at": item.published_at.isoformat() if item.published_at else None,
            "relevance_score": item.relevance_score,
            "matched_keywords": item.matched_keywords,
        }
        for item in news_result.items[:NEWS_MAX_NEWS_FOR_DISPLAY]
    ]

    # 选择 Prompt 模板
    from app.services.ai_prompt_templates import get_template
    template = get_template(profile.fund_type)

    # 构建分析上下文
    freshness_note = _build_holdings_freshness_note(fund_code)
    extra_info = _build_extra_info(fund_code, profile.fund_type)

    context = template.__class__.__bases__[0].AnalysisContext(
        fund_code=fund_code,
        fund_name=profile.fund_name,
        fund_type=profile.fund_type,
        fund_type_display=_get_fund_type_display(profile.fund_type),
        estimated_return=estimation_return,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
        source=source,
        holdings_freshness_note=freshness_note,
        news_items=news_items_for_prompt,
        extra_info=extra_info,
    )

    # 组装 Prompt
    prompt = template.build_prompt(context)

    # 调用 AI Provider
    primary_client = _create_primary_client()
    fallback_client = _create_fallback_client()

    response_text = None
    used_provider = None
    used_model = None

    try:
        if primary_client:
            try:
                response_text = await primary_client.chat(prompt)
                used_provider = AI_PRIMARY_PROVIDER
                used_model = AI_PRIMARY_MODEL
            except AIProviderError as e:
                logger.warning(
                    "primary_provider_failed provider=%s error=%s switching_to_fallback",
                    e.provider, e
                )
                if fallback_client and AI_FALLBACK_ON_ERROR:
                    response_text = await fallback_client.chat(prompt)
                    used_provider = AI_FALLBACK_PROVIDER
                    used_model = AI_FALLBACK_MODEL
                else:
                    raise

        elif fallback_client:
            response_text = await fallback_client.chat(prompt)
            used_provider = AI_FALLBACK_PROVIDER
            used_model = AI_FALLBACK_MODEL

        else:
            raise AIProviderError(
                "无可用的 AI Provider",
                provider="none"
            )

    finally:
        if primary_client:
            await primary_client.close()
        if fallback_client:
            await fallback_client.close()

    # 解析响应
    analysis = template.parse_response(response_text, AI_ALLOWED_ACTIONS)

    # 写入缓存
    _write_ai_cache(
        fund_code=fund_code,
        source=source,
        analysis=analysis,
        provider_used=used_provider or "unknown",
        model_used=used_model or "unknown",
        news_count=len(news_items_for_prompt),
    )

    # 构建持仓数据信息
    holdings_data_info = _build_holdings_data_info(fund_code)

    result = {
        "fund_code": fund_code,
        "fund_name": profile.fund_name,
        "fund_type": profile.fund_type,
        "analysis": analysis,
        "news_used": news_items_for_display,
        "holdings_data_info": holdings_data_info,
        "provider_used": used_provider,
        "model_used": used_model,
        "cached": False,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }

    logger.info(
        "ai_analysis_complete fund_code=%s source=%s provider=%s model=%s news_count=%d",
        fund_code, source, used_provider, used_model, len(news_items_for_prompt)
    )

    return result


async def get_news(fund_code: str, limit: int = 5, source: str = "all") -> dict:
    """获取基金相关新闻列表（独立接口，不调用 AI）

    Args:
        fund_code: 基金代码
        limit: 返回条数（最多10）
        source: 新闻来源过滤 ("cls"/"em"/"all")

    Returns:
        新闻列表结果字典
    """
    set_log_context(fund_code=fund_code, stage="news_fetch")

    from app.services.news_service import fetch_relevant_news
    result = await fetch_relevant_news(fund_code, limit=min(limit, 10))

    # 来源过滤
    items = result.items
    if source != "all":
        items = [item for item in items if item.source_type == source]

    news_list = [
        {
            "title": item.title,
            "content": item.content[:200] if item.content else "",
            "source": item.source,
            "source_type": item.source_type,
            "url": item.url,
            "published_at": item.published_at.isoformat() if item.published_at else None,
            "relevance_score": item.relevance_score,
            "matched_keywords": item.matched_keywords,
        }
        for item in items
    ]

    return {
        "fund_code": fund_code,
        "news": news_list,
        "total": len(news_list),
        "fetched_at": result.fetched_at.isoformat(timespec="seconds"),
    }


async def get_provider_status() -> dict:
    """获取 AI Provider 可用性状态

    Returns:
        Provider 状态字典
    """
    primary_client = _create_primary_client()
    fallback_client = _create_fallback_client()

    result = {"primary": None, "fallback": None}

    try:
        if primary_client:
            status = await primary_client.health_check()
            result["primary"] = {
                "provider": status.provider,
                "model": status.model,
                "status": status.status,
                "latency_ms": status.latency_ms,
                "last_checked": status.last_checked.isoformat() if status.last_checked else None,
            }
        else:
            result["primary"] = {
                "provider": AI_PRIMARY_PROVIDER,
                "model": AI_PRIMARY_MODEL,
                "status": "not_configured",
                "latency_ms": None,
                "last_checked": None,
            }
    except Exception as e:
        logger.error("primary_health_check_error error=%s", e)
        result["primary"] = {
            "provider": AI_PRIMARY_PROVIDER,
            "model": AI_PRIMARY_MODEL,
            "status": "error",
            "error": str(e),
        }

    try:
        if fallback_client:
            status = await fallback_client.health_check()
            result["fallback"] = {
                "provider": status.provider,
                "model": status.model,
                "status": status.status,
                "latency_ms": status.latency_ms,
                "last_checked": status.last_checked.isoformat() if status.last_checked else None,
            }
        else:
            result["fallback"] = {
                "provider": AI_FALLBACK_PROVIDER,
                "model": AI_FALLBACK_MODEL,
                "status": "not_configured",
                "latency_ms": None,
                "last_checked": None,
            }
    except Exception as e:
        logger.error("fallback_health_check_error error=%s", e)
        result["fallback"] = {
            "provider": AI_FALLBACK_PROVIDER,
            "model": AI_FALLBACK_MODEL,
            "status": "error",
            "error": str(e),
        }

    if primary_client:
        await primary_client.close()
    if fallback_client:
        await fallback_client.close()

    return result


def _get_fund_type_display(fund_type: str) -> str:
    """获取基金类型的中文显示名

    Args:
        fund_type: 基金类型标识

    Returns:
        中文显示名
    """
    type_display_map = {
        "equity_active": "偏股/主动股票型",
        "equity_index": "指数/ETF型",
        "bond": "债券型",
        "mixed_equity": "平衡混合型",
        "hybrid_flexible": "灵活配置型",
        "money_market": "货币型",
        "fof": "FOF型",
    }
    return type_display_map.get(fund_type, fund_type)


def _build_holdings_data_info(fund_code: str) -> dict:
    """构建持仓数据时效信息

    Args:
        fund_code: 基金代码

    Returns:
        持仓数据信息字典
    """
    default_info = {
        "quarter": "未知",
        "days_since_report": None,
        "freshness_level": "unknown",
        "freshness_warning": "暂无持仓数据",
    }

    try:
        from app.services.holding_service import get_latest_holdings
        holdings = get_latest_holdings(fund_code)

        if not holdings:
            return default_info

        report_date_str = holdings[0].get("report_date", "")
        if not report_date_str:
            return default_info

        report_date = datetime.strptime(report_date_str, "%Y-%m-%d").date()
        days_since = (date.today() - report_date).days
        quarter = f"{report_date.year}Q{(report_date.month - 1) // 3 + 1}"

        if days_since <= 30:
            level = "fresh"
            warning = f"持仓数据来源：{quarter}季报，距今{days_since}天，准确性高"
        elif days_since <= 60:
            level = "medium"
            warning = f"持仓数据来源：{quarter}季报，距今{days_since}天，准确性适中"
        else:
            level = "stale"
            warning = f"持仓数据来源：{quarter}季报，距今{days_since}天，准确性降低"

        return {
            "quarter": quarter,
            "days_since_report": days_since,
            "freshness_level": level,
            "freshness_warning": warning,
        }

    except Exception as e:
        logger.debug("holdings_data_info_error fund_code=%s error=%s", fund_code, e)
        return default_info
