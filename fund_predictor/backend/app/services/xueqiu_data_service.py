import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any

import requests

from app.core.errors import DataFetchError

logger = logging.getLogger(__name__)


class XueqiuAuthError(DataFetchError):
    code = "XUEQIU_AUTH_ERROR"
    stage = "xueqiu_auth"
    http_status = 401


class XueqiuRateLimitError(DataFetchError):
    code = "XUEQIU_RATE_LIMIT"
    stage = "xueqiu_rate_limit"
    http_status = 429


class XueqiuDataService:
    BASE_URL = "https://stock.xueqiu.com"

    DEFAULT_COOKIE_DICT = {
        "xq_a_token": "20458f74230aee45906ecb90d8c70ff43daa3837",
        "xqat": "20458f74230aee45906ecb90d8c70ff43daa3837",
        "xq_r_token": "fa5fac8aea31fef0733c31a1c3670554e9365bda",
        "xq_id_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJ1aWQiOi0xLCJpc3MiOiJ1YyIsImV4cCI6MTc4MTA1NDU5NiwiY3RtIjoxNzc5NjkzNTM2Nzc3LCJjaWQiOiJkOWQwbjRBWnVwIn0.q6KBEn4mP3gcuoHu5Ydu3EQvGBqnfhss7ffOM63KZkTXa_hi_PlmJlRY3XeiyslFIeyNHJkk6DiZHwBzLcJKqmDt0YhgoQflGdRCouQj5R69Ds3SSe-HdliB4l3RV4gdHAUs7yC2lGZKdU0et8CjTqv3LiA2GGOEzkFwG-Sr-iSeuY0Zveht6zd1uWUJVDCmcgT_zKDyMOGrUziQwJHOIGlzCRV45mckDS3bpIVOYwLortL7ubNBw05CkpJ_xD23di-4vitOCSoMKD6fJCdhPX95LL2RTXpoQleHyd4Trhuw51uycGhpS14FYbuTnBi_mfmJblwZXfyqw-WU2XjzIQ",
        "cookiesu": "601779693564189",
        "u": "601779693564189",
        "device_id": "226d8fefef0a0dd96f9820304f458f5f",
        "is_overseas": "0"
    }

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://xueqiu.com",
        "Origin": "https://xueqiu.com",
    }

    MAX_RETRIES = 3
    RETRY_DELAYS = [1, 2, 4]
    REQUEST_TIMEOUT = 30
    CACHE_TTL = 300

    def __init__(self, cookie: dict[str, str] | None = None):
        self.cookie_dict = cookie or self.DEFAULT_COOKIE_DICT
        self.session = requests.Session()
        self._setup_session()
        self._cache: dict[str, tuple[Any, float]] = {}
        self._cache_lock = threading.RLock()
        self._semaphore = threading.Semaphore(5)

    def _setup_session(self):
        self.session.headers.update(self.HEADERS)
        self.session.cookies.update(self.cookie_dict)

    def _get_cache(self, key: str) -> Any | None:
        with self._cache_lock:
            if key in self._cache:
                data, timestamp = self._cache[key]
                if time.time() - timestamp < self.CACHE_TTL:
                    return data
                del self._cache[key]
        return None

    def _set_cache(self, key: str, data: Any, ttl: int | None = None):
        with self._cache_lock:
            self._cache[key] = (data, time.time())

    def _clear_cache(self, symbol: str | None = None):
        with self._cache_lock:
            if symbol is None:
                self._cache.clear()
            else:
                keys_to_remove = [k for k in self._cache if k.endswith(f":{symbol}")]
                for k in keys_to_remove:
                    del self._cache[k]

    def _request(self, url: str, params: dict[str, Any] | None = None) -> dict:
        for attempt in range(self.MAX_RETRIES):
            try:
                with self._semaphore:
                    start_time = time.time()
                    logger.info("xueqiu_request_start url=%s params=%s attempt=%s", url, params, attempt + 1)

                    response = self.session.get(
                        url,
                        params=params,
                        timeout=self.REQUEST_TIMEOUT,
                    )

                    elapsed_ms = (time.time() - start_time) * 1000

                    logger.info(
                        "xueqiu_request_complete url=%s status_code=%s elapsed_ms=%.0f",
                        url,
                        response.status_code,
                        elapsed_ms,
                    )

                    return self._parse_response(response)

            except requests.exceptions.Timeout as exc:
                logger.warning("xueqiu_request_timeout url=%s attempt=%s error=%s", url, attempt + 1, exc)
                if attempt < self.MAX_RETRIES - 1:
                    delay = self.RETRY_DELAYS[attempt]
                    logger.info("xueqiu_retry_wait url=%s delay=%ss", url, delay)
                    time.sleep(delay)
                else:
                    raise DataFetchError(
                        f"Request timeout after {self.MAX_RETRIES} attempts",
                        details={"url": url, "params": params, "error": str(exc)},
                    ) from exc

            except requests.exceptions.ConnectionError as exc:
                logger.warning(
                    "xueqiu_request_connection_error url=%s attempt=%s error=%s", url, attempt + 1, exc
                )
                if attempt < self.MAX_RETRIES - 1:
                    delay = self.RETRY_DELAYS[attempt]
                    logger.info("xueqiu_retry_wait url=%s delay=%ss", url, delay)
                    time.sleep(delay)
                else:
                    raise DataFetchError(
                        f"Connection error after {self.MAX_RETRIES} attempts",
                        details={"url": url, "params": params, "error": str(exc)},
                    ) from exc

            except requests.exceptions.RequestException as exc:
                logger.error("xueqiu_request_error url=%s error=%s", url, exc)
                raise DataFetchError(
                    f"Request failed: {exc}",
                    details={"url": url, "params": params, "error": str(exc)},
                ) from exc

        raise DataFetchError("Unexpected request failure", details={"url": url})

    def _parse_response(self, response: requests.Response) -> dict:
        try:
            data = response.json()
        except (ValueError, requests.exceptions.JSONDecodeError) as exc:
            raise DataFetchError(
                "Failed to parse JSON response",
                details={
                    "status_code": response.status_code,
                    "response_text": response.text[:500],
                    "error": str(exc),
                },
            ) from exc

        error_code = data.get("error_code")
        if error_code == 400016:
            raise XueqiuAuthError(
                "Authentication failed or cookie expired",
                details={
                    "error_code": error_code,
                    "error_msg": data.get("error_description", "Unknown auth error"),
                },
            )
        if error_code and error_code != 0:
            if error_code in (429, 430):
                raise XueqiuRateLimitError(
                    "Rate limit exceeded",
                    details={"error_code": error_code},
                )
            raise DataFetchError(
                f"API returned error code: {error_code}",
                details={
                    "error_code": error_code,
                    "response_data": str(data)[:500],
                },
            )

        return data

    def fetch_index_quote(self, symbol: str) -> dict[str, Any]:
        """获取指数/股票实时行情"""
        cache_key = f"fetch_index_quote:{symbol}"
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached

        url = f"{self.BASE_URL}/v5/stock/quote.json"
        params = {"symbol": symbol, "extend": "detail"}

        data = self._request(url, params)
        quote_data = data.get("data", {}).get("quote")

        if not quote_data:
            raise DataFetchError(
                "No quote data found",
                details={"symbol": symbol},
            )

        result = {
            "symbol": quote_data.get("symbol"),
            "name": quote_data.get("name"),
            "current": quote_data.get("current"),
            "percent": quote_data.get("percent"),
            "chg": quote_data.get("chg"),
            "open": quote_data.get("open"),
            "high": quote_data.get("high"),
            "low": quote_data.get("low"),
            "last_close": quote_data.get("last_close"),
            "volume": quote_data.get("volume"),
            "amount": quote_data.get("amount"),
            "timestamp": quote_data.get("timestamp"),
            "market_capital": quote_data.get("market_capital"),
            "turnover_rate": quote_data.get("turnover_rate"),
            "high52w": quote_data.get("high52w"),
            "low52w": quote_data.get("low52w"),
            "source": "xueqiu",
        }

        self._set_cache(cache_key, result)
        logger.info("xueqiu_index_quote_fetched symbol=%s name=%s current=%s", symbol, result.get("name"), result.get("current"))

        return result

    def fetch_minute_chart(self, symbol: str, period: str = "1d") -> list[dict[str, Any]]:
        """获取分时数据"""
        cache_key = f"fetch_minute_chart:{symbol}:{period}"
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached

        url = f"{self.BASE_URL}/v5/stock/chart/minute.json"
        params = {"symbol": symbol, "period": period}

        data = self._request(url, params)
        items = data.get("data", {}).get("items", [])

        if not items:
            raise DataFetchError(
                "No minute chart data found",
                details={"symbol": symbol, "period": period},
            )

        result = []
        for item in items:
            timestamp_ms = item.get("timestamp")
            dt = None
            time_str = None
            if timestamp_ms:
                try:
                    dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
                    time_str = dt.strftime("%H:%M")
                except (OSError, ValueError, TypeError):
                    pass

            record = {
                "date": dt,
                "time": time_str,
                "current": item.get("current"),
                "avg_price": item.get("avg_price"),
                "volume": item.get("volume"),
                "amount": item.get("amount"),
                "chg": item.get("chg"),
                "percent": item.get("percent"),
                "high": item.get("high"),
                "low": item.get("low"),
                "volume_total": item.get("volume_total"),
                "amount_total": item.get("amount_total"),
            }
            result.append(record)

        self._set_cache(cache_key, result)
        logger.info("xueqiu_minute_chart_fetched symbol=%s points=%s", symbol, len(result))

        return result

    def fetch_kline_data(
        self,
        symbol: str,
        begin: int | None = None,
        period: str = "day",
        type: str = "before",
        count: int = -284,
        indicator: str = "kline,pe,pb,ps,pcf,market_capital,agt,ggt,balance",
    ) -> list[dict[str, Any]]:
        """获取K线数据（已验证可用 ✅）

        Args:
            symbol: 股票代码（如 SH000001, SH600519）
            begin: 开始时间戳（毫秒），默认为当前时间
            period: 周期（day/week/month/quarter/year/1m/5m/15m/30m/60m）
            type: 复权类型（before=前复权, after=后复权, normal=不复权）
            count: 数量（负数表示从begin向前取）
            indicator: 指标（kline,pe,pb,ps,pcf,market_capital,...）

        Returns:
            K线数据列表，每条记录包含所有请求的指标字段

        实际返回格式示例（2026-05-25验证通过）：
            column: ["timestamp","volume","open","high","low","close","chg","percent",
                    "turnoverrate","amount","volume_post","amount_post","pe","pb","ps",
                    "pcf","market_capital","balance","hold_volume_cn","hold_ratio_cn",
                    "net_volume_cn","hold_volume_hk","hold_ratio_hk","net_volume_hk"]
            item: [1742486400000, 52086263000, 3401.76, 3414.71, 3355.84, 3364.83,
                   -44.12, -1.29, 1.14, 623164007297.2, ...]
        """
        cache_key = f"fetch_kline_data:{symbol}:{period}:{type}:{indicator}"
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached

        url = f"{self.BASE_URL}/v5/stock/chart/kline.json"

        if begin is None:
            begin = int(datetime.now().timestamp() * 1000)

        params = {
            "symbol": symbol,
            "begin": begin,
            "period": period,
            "type": type,
            "count": count,
            "indicator": indicator,
        }

        logger.info(
            "xueqiu_kline_request symbol=%s begin=%s period=%s type=%s count=%s",
            symbol, begin, period, type, count,
        )

        data = self._request(url, params)
        response_data = data.get("data", {})
        columns = response_data.get("column", [])
        items = response_data.get("item", [])

        if not items:
            logger.warning(
                "xueqiu_kline_empty_response symbol=%s columns=%s",
                symbol, len(columns),
            )
            return []

        result = []
        for item in items:
            record = {"source": "xueqiu"}
            for idx, col_name in enumerate(columns):
                if idx < len(item):
                    value = item[idx]
                    if col_name == "timestamp" and value is not None:
                        try:
                            record["date"] = datetime.fromtimestamp(value / 1000, tz=timezone.utc).date()
                            record["timestamp"] = value
                        except (ValueError, OSError, TypeError):
                            record[col_name] = value
                    else:
                        record[col_name] = value
            result.append(record)

        self._set_cache(cache_key, result)
        logger.info(
            "xueqiu_kline_fetched symbol=%s records=%s columns=%s first_date=%s last_date=%s",
            symbol, len(result), len(columns),
            result[0].get("date") if result else None,
            result[-1].get("date") if result else None,
        )

        return result


_xueqiu_instance: XueqiuDataService | None = None
_xueqiu_lock = threading.Lock()


def get_xueqiu_service(cookie: str | None = None) -> XueqiuDataService:
    global _xueqiu_instance
    with _xueqiu_lock:
        if _xueqiu_instance is None:
            _xueqiu_instance = XueqiuDataService(cookie)
        return _xueqiu_instance
