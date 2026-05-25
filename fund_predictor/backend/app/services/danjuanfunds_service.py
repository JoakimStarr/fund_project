import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import requests

from app.core.errors import DataFetchError

logger = logging.getLogger(__name__)


class DanjuanFundsService:
    BASE_URL = "https://danjuanfunds.com"
    
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://danjuanfunds.com",
    }
    
    MAX_RETRIES = 3
    RETRY_DELAYS = [1, 2, 4]
    REQUEST_TIMEOUT = 30
    CACHE_TTL = 3600
    
    def __init__(self):
        self.session = requests.Session()
        self._setup_session()
        self._cache: dict[str, tuple[Any, float]] = {}
        self._cache_lock = threading.RLock()
        self._semaphore = threading.Semaphore(5)
    
    def _setup_session(self):
        self.session.headers.update(self.HEADERS)
    
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
    
    def _clear_cache(self, fund_code: str | None = None):
        with self._cache_lock:
            if fund_code is None:
                self._cache.clear()
            else:
                keys_to_remove = [k for k in self._cache if k.endswith(f":{fund_code}")]
                for k in keys_to_remove:
                    del self._cache[k]
    
    def _request(self, endpoint: str, params: dict[str, Any] | None = None) -> dict:
        url = f"{self.BASE_URL}{endpoint}"
        
        for attempt in range(self.MAX_RETRIES):
            try:
                with self._semaphore:
                    start_time = time.time()
                    logger.info("danjuan_request_start url=%s params=%s attempt=%s", url, params, attempt + 1)
                    
                    response = self.session.get(
                        url,
                        params=params,
                        timeout=self.REQUEST_TIMEOUT,
                    )
                    
                    elapsed_ms = (time.time() - start_time) * 1000
                    
                    logger.info(
                        "danjuan_request_complete url=%s status_code=%s elapsed_ms=%.0f",
                        url,
                        response.status_code,
                        elapsed_ms,
                    )
                    
                    return self._parse_response(response)
                    
            except requests.exceptions.Timeout as exc:
                logger.warning("danjuan_request_timeout url=%s attempt=%s error=%s", url, attempt + 1, exc)
                if attempt < self.MAX_RETRIES - 1:
                    delay = self.RETRY_DELAYS[attempt]
                    logger.info("danjuan_retry_wait url=%s delay=%ss", url, delay)
                    time.sleep(delay)
                else:
                    raise DataFetchError(
                        f"Request timeout after {self.MAX_RETRIES} attempts",
                        details={"url": url, "params": params, "error": str(exc)},
                    ) from exc
                    
            except requests.exceptions.ConnectionError as exc:
                logger.warning("danjuan_request_connection_error url=%s attempt=%s error=%s", url, attempt + 1, exc)
                if attempt < self.MAX_RETRIES - 1:
                    delay = self.RETRY_DELAYS[attempt]
                    logger.info("danjuan_retry_wait url=%s delay=%ss", url, delay)
                    time.sleep(delay)
                else:
                    raise DataFetchError(
                        f"Connection error after {self.MAX_RETRIES} attempts",
                        details={"url": url, "params": params, "error": str(exc)},
                    ) from exc
                    
            except requests.exceptions.RequestException as exc:
                logger.error("danjuan_request_error url=%s error=%s", url, exc)
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
        
        result_code = data.get("result_code")
        if result_code and str(result_code) != "200":
            error_msg = data.get("error_msg", data.get("message", "Unknown API error"))
            raise DataFetchError(
                f"API returned error code: {result_code}",
                details={
                    "result_code": result_code,
                    "error_msg": error_msg,
                    "response_data": str(data)[:500],
                },
            )
        
        return data
    
    def fetch_fund_nav_history(self, fund_code: str, page: int = 1, size: int = 20) -> pd.DataFrame:
        cache_key = f"fetch_fund_nav_history:{fund_code}"
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached
        
        all_records = []
        current_page = page
        total_pages = 1
        
        while current_page <= total_pages or current_page == 1:
            try:
                endpoint = f"/djapi/fund/nav/history/{fund_code}"
                params = {"page": current_page, "size": size}
                
                data = self._request(endpoint, params)
                
                items = data.get("data", {}).get("items", [])
                if not items:
                    break
                
                pagination_info = data.get("data", {}).get("pagination_info", {})
                total_pages = pagination_info.get("total_pages", 1)
                
                for item in items:
                    record = {
                        "date": None,
                        "nav": None,
                        "daily_growth_pct": None,
                        "acc_nav": None,
                        "source": "danjuanfunds",
                    }
                    
                    date_str = item.get("date") or item.get("report_date")
                    if date_str:
                        try:
                            record["date"] = pd.to_datetime(date_str, errors="coerce")
                        except Exception:
                            pass
                    
                    nav_val = item.get("nav") or item.get("unit_nav")
                    if nav_val is not None:
                        try:
                            record["nav"] = float(nav_val)
                        except (ValueError, TypeError):
                            pass
                    
                    acc_nav_val = item.get("acc_nav") or item.get("accumulated_nav")
                    if acc_nav_val is not None:
                        try:
                            record["acc_nav"] = float(acc_nav_val)
                        except (ValueError, TypeError):
                            pass
                    
                    percentage = item.get("percentage")
                    if percentage is not None:
                        try:
                            record["daily_growth_pct"] = float(percentage)
                        except (ValueError, TypeError):
                            pass
                    
                    all_records.append(record)
                
                if current_page >= total_pages:
                    break
                    
                current_page += 1
                
            except DataFetchError as exc:
                if current_page == 1:
                    raise
                logger.warning("danjuan_nav_pagination_error fund_code=%s page=%s error=%s", fund_code, current_page, exc)
                break
        
        if not all_records:
            raise DataFetchError(
                "No NAV history data found",
                details={"fund_code": fund_code},
            )
        
        df = pd.DataFrame(all_records)
        df = df.dropna(subset=["date", "nav"]).sort_values("date").drop_duplicates("date").reset_index(drop=True)
        
        if len(df) == 0:
            raise DataFetchError(
                "NAV history data is empty after cleaning",
                details={"fund_code": fund_code},
            )
        
        self._set_cache(cache_key, df)
        logger.info("danjuan_fund_nav_history_fetched fund_code=%s rows=%s", fund_code, len(df))
        
        return df
    
    def fetch_fund_info(self, fund_code: str) -> dict[str, Any]:
        cache_key = f"fetch_fund_info:{fund_code}"
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached
        
        endpoint = "/djapi/fundx/autoinvest/quote/fund/info"
        params = {"fd_codes": fund_code}
        
        data = self._request(endpoint, params)
        items = data.get("data", {}).get("items", [])
        
        if not items:
            raise DataFetchError(
                "No fund info found",
                details={"fund_code": fund_code},
            )
        
        fund_item = items[0]
        result = {
            "fd_code": fund_item.get("fd_code", fund_code),
            "fd_name": fund_item.get("fd_name"),
            "fd_full_name": fund_item.get("fd_full_name"),
            "fd_type_desc": fund_item.get("fd_type_desc"),
        }
        
        self._set_cache(cache_key, result)
        logger.info("danjuan_fund_info_fetched fund_code=%s name=%s", fund_code, result.get("fd_name"))
        
        return result
    
    def fetch_fund_growth(self, fund_code: str) -> list[dict[str, Any]]:
        cache_key = f"fetch_fund_growth:{fund_code}"
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached
        
        endpoint = f"/djapi/fund/growth/{fund_code}"
        params = {"day": "ty"}
        
        data = self._request(endpoint, params)
        items = data.get("data", [])
        
        if not items:
            raise DataFetchError(
                "No growth data found",
                details={"fund_code": fund_code},
            )
        
        result = []
        for item in items:
            record = {
                "date": item.get("date"),
                "nav": item.get("nav"),
                "value": item.get("value"),
                "than_value": item.get("than_value"),
                "performance_value": item.get("performance_value"),
            }
            result.append(record)
        
        self._set_cache(cache_key, result)
        logger.info("danjuan_fund_growth_fetched fund_code=%s rows=%s", fund_code, len(result))
        
        return result
    
    def fetch_risk_analysis(self, fund_code: str) -> list[dict[str, Any]]:
        cache_key = f"fetch_risk_analysis:{fund_code}"
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached
        
        endpoint = f"/djapi/fund/base/quote/data/index/analysis/{fund_code}"
        
        data = self._request(endpoint)
        analysis_list = data.get("data", {}).get("analysis_list", [])
        
        if not analysis_list:
            raise DataFetchError(
                "No risk analysis data found",
                details={"fund_code": fund_code},
            )
        
        result = []
        for item in analysis_list:
            record = {
                "period": item.get("index_name") or item.get("period"),
                "volatility_rank": item.get("volatility_rank"),
                "sharpe_rank": item.get("sharpe_rank"),
                "max_draw_down": item.get("max_draw_down"),
            }
            result.append(record)
        
        self._set_cache(cache_key, result)
        logger.info("danjuan_risk_analysis_fetched fund_code=%s periods=%s", fund_code, len(result))
        
        return result
    
    def fetch_achievement(self, fund_code: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        cache_key = f"fetch_achievement:{fund_code}"
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached
        
        endpoint = f"/djapi/fundx/base/fund/achievement/{fund_code}"
        
        data = self._request(endpoint)
        achievement_data = data.get("data", {})
        
        annual_performance_raw = achievement_data.get("annual_performance_list", []) or []
        stage_performance_raw = achievement_data.get("stage_performance_list", []) or []
        
        annual_performance = []
        for item in annual_performance_raw:
            record = {
                "year": item.get("year"),
                "return_rate": item.get("return_rate"),
                "rank_percent": item.get("rank_percent"),
                "benchmark_return": item.get("benchmark_return"),
            }
            annual_performance.append(record)
        
        stage_performance = []
        for item in stage_performance_raw:
            record = {
                "stage_type": item.get("stage_type") or item.get("type"),
                "return_rate": item.get("return_rate"),
                "rank_percent": item.get("rank_percent"),
                "benchmark_return": item.get("benchmark_return"),
            }
            stage_performance.append(record)
        
        result = (annual_performance, stage_performance)
        self._set_cache(cache_key, result)
        logger.info(
            "danjuan_achievement_fetched fund_code=%s annual=%s stage=%s",
            fund_code,
            len(annual_performance),
            len(stage_performance),
        )
        
        return result
    
    def fetch_manager(self, fund_code: str) -> dict[str, Any]:
        cache_key = f"fetch_manager:{fund_code}"
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached
        
        endpoint = "/djapi/fundx/base/fund/record/manager/list"
        params = {"fund_code": fund_code, "post_status": "1"}
        
        data = self._request(endpoint, params)
        manager_list = data.get("data", {}).get("manager_list", []) or data.get("data", {}).get("items", [])
        
        if not manager_list:
            raise DataFetchError(
                "No manager information found",
                details={"fund_code": fund_code},
            )
        
        manager = manager_list[0]
        result = {
            "name": manager.get("name"),
            "work_year": manager.get("work_year"),
            "cp_rate": manager.get("cp_rate"),
            "performance_year": manager.get("performance_year"),
        }
        
        self._set_cache(cache_key, result)
        logger.info("danjuan_manager_fetched fund_code=%s name=%s", fund_code, result.get("name"))
        
        return result
    
    def fetch_stock_industry_contribution(self, fund_code: str, period_time: str = "2025") -> dict[str, Any]:
        cache_key = f"fetch_stock_industry_contribution:{fund_code}:{period_time}"
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached
        
        endpoint = "/djapi/fundx/base/fund/achievement/analysis/stock"
        params = {"fund_code": fund_code, "period_time": period_time}
        
        data = self._request(endpoint, params)
        contribution_data = data.get("data", {})
        
        industry_analysis = contribution_data.get("industry_analysis_list", {}) or {}
        stock_analysis = contribution_data.get("stock_analysis_list", {}) or {}
        
        result = {
            "industry_analysis_list": {
                "top_list": industry_analysis.get("top_list", []),
                "tail_list": industry_analysis.get("tail_list", []),
            },
            "stock_analysis_list": {
                "top_list": stock_analysis.get("top_list", []),
                "tail_list": stock_analysis.get("tail_list", []),
            },
        }
        
        self._set_cache(cache_key, result)
        logger.info("danjuan_stock_industry_fetched fund_code=%s period=%s", fund_code, period_time)
        
        return result
    
    def fetch_profit_ratio(self, fund_code: str) -> dict[str, Any]:
        cache_key = f"fetch_profit_ratio:{fund_code}"
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached
        
        endpoint = f"/djapi/fundx/base/fund/profit/ratio/{fund_code}"
        
        data = self._request(endpoint)
        profit_data = data.get("data", {})
        
        raw_data_list = profit_data.get("data_list", []) or []
        data_list = []
        for item in raw_data_list:
            record = {
                "holding_time": item.get("holding_time"),
                "profit_ratio": item.get("profit_ratio"),
                "average_income": item.get("average_income"),
            }
            data_list.append(record)
        
        result = {
            "holding_year": profit_data.get("holding_year"),
            "profit_ratio_desc": profit_data.get("profit_ratio_desc"),
            "data_list": data_list,
        }
        
        self._set_cache(cache_key, result)
        logger.info("danjuan_profit_ratio_fetched fund_code=%s entries=%s", fund_code, len(data_list))
        
        return result
    
    def fetch_trade_date(self, fund_code: str) -> dict[str, Any]:
        cache_key = f"fetch_trade_date:{fund_code}"
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached
        
        endpoint = "/djapi/fund/order/v2/trade_date"
        params = {"fd_code": fund_code}
        
        data = self._request(endpoint, params)
        trade_date_data = data.get("data", {})
        
        result = {
            "buy_query_date": trade_date_data.get("buy_query_date"),
            "buy_confirm_date": trade_date_data.get("buy_confirm_date"),
            "sale_query_date": trade_date_data.get("sale_query_date"),
            "sale_confirm_date": trade_date_data.get("sale_confirm_date"),
        }
        
        self._set_cache(cache_key, result)
        logger.info("danjuan_trade_date_fetched fund_code=%s buy_query=%s", fund_code, result.get("buy_query_date"))
        
        return result


_danjuan_service_instance: DanjuanFundsService | None = None
_service_lock = threading.Lock()


def get_danjuan_service() -> DanjuanFundsService:
    global _danjuan_service_instance
    with _service_lock:
        if _danjuan_service_instance is None:
            _danjuan_service_instance = DanjuanFundsService()
        return _danjuan_service_instance
