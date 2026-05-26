import asyncio
import logging
import requests
from app.core.config import settings

logger = logging.getLogger(__name__)
SINA_HEADERS = {
    "Referer": "https://finance.sina.com.cn",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}
INDEX_SINA_MAP = {
    "sh000001": "上证指数",
    "sz399001": "深证成指",
    "sz399006": "创业板指",
    "sh000688": "科创50",
    "sh000016": "上证50",
    "sh000300": "沪深300",
    "sh000905": "中证500",
    "sh000852": "中证1000",
}
XQ_INDEX_MAP = {
    "SH000001": "上证指数",
    "SZ399001": "深证成指",
    "SZ399006": "创业板指",
    "SH000688": "科创50",
    "SH000016": "上证50",
    "SH000300": "沪深300",
    "SH000905": "中证500",
    "SH000852": "中证1000",
}


def _fetch_sina_block(codes: list[str]) -> str:
    formatted = []
    for code in codes:
        if code.startswith("6") or code.startswith("5"):
            formatted.append(f"sh{code}")
        else:
            formatted.append(f"sz{code}")
    url = f"http://hq.sinajs.cn/list={','.join(formatted)}"
    resp = requests.get(url, headers=SINA_HEADERS, timeout=5)
    resp.encoding = "gbk"
    return resp.text


def _parse_sina_line(line: str) -> tuple:
    if "hq_str_" not in line or '""' in line:
        return None, None
    code_part = line.split('"')[0].replace("var hq_str_", "").strip("=")
    actual_code = code_part.replace("sh", "").replace("sz", "")
    data = line.split('"')[1].split(",")
    if len(data) < 32:
        return None, None
    prev_close = float(data[2]) if data[2] else 0
    price = float(data[3]) if data[3] else 0
    pct = (price - prev_close) / prev_close if prev_close > 0 else 0
    return actual_code, {
        "name": data[0],
        "open": float(data[1]) if data[1] else 0,
        "prev_close": prev_close,
        "price": price,
        "high": float(data[4]) if data[4] else 0,
        "low": float(data[5]) if data[5] else 0,
        "pct_change": round(pct, 4),
        "volume": int(data[8]) if data[8] else 0,
    }


async def get_sina_realtime(stock_codes: list[str]) -> dict:
    loop = asyncio.get_running_loop()
    text = await loop.run_in_executor(None, _fetch_sina_block, stock_codes)
    result = {}
    for line in text.strip().split("\n"):
        actual_code, parsed = _parse_sina_line(line)
        if actual_code:
            result[actual_code] = parsed
    return result


async def get_sina_index_realtime() -> dict:
    codes = list(INDEX_SINA_MAP.keys())
    loop = asyncio.get_running_loop()
    text = await loop.run_in_executor(None, _fetch_sina_block, codes)
    result = {}
    for line in text.strip().split("\n"):
        actual_code, parsed = _parse_sina_line(line)
        if actual_code:
            result[actual_code] = parsed
    return result


async def get_xueqiu_realtime(symbols: list[str]) -> dict:
    try:
        from app.services.data.danjuan_client import batch_quotes_xueqiu
        results = await batch_quotes_xueqiu(symbols)
        output = {}
        for sym, q in results.items():
            if q is None:
                continue
            clean_sym = sym.replace("SH", "").replace("SZ", "")
            prev_close = q.get("last_close", 0) or 0
            current = q.get("current", 0) or 0
            pct = q.get("percent", 0) or 0
            output[clean_sym] = {
                "name": q.get("name", ""),
                "open": q.get("open", 0) or 0,
                "prev_close": prev_close,
                "price": current,
                "high": q.get("high", 0) or 0,
                "low": q.get("low", 0) or 0,
                "pct_change": round(pct / 100.0, 4) if pct != 0 else 0,
                "volume": int(q.get("volume", 0) or 0),
            }
        return output
    except Exception as e:
        logger.warning(f"雪球实时行情获取失败: {e}, 回退到新浪")
        sina_codes = [s.replace("SH", "").replace("SZ", "") for s in symbols]
        return await get_sina_realtime(sina_codes)


async def get_index_realtime() -> dict:
    try:
        symbols = list(XQ_INDEX_MAP.keys())
        results = await batch_quotes_xueqiu(symbols)
        output = {}
        for sym, q in results.items():
            if q is None:
                continue
            clean_sym = sym.replace("SH", "").replace("SZ", "")
            pct = q.get("percent", 0) or 0
            output[clean_sym] = {
                "name": XQ_INDEX_MAP.get(sym, ""),
                "open": q.get("open", 0) or 0,
                "prev_close": q.get("last_close", 0) or 0,
                "price": q.get("current", 0) or 0,
                "high": q.get("high", 0) or 0,
                "low": q.get("low", 0) or 0,
                "pct_change": round(pct / 100.0, 4) if pct != 0 else 0,
                "volume": int(q.get("volume", 0) or 0),
            }
        return output
    except Exception as e:
        logger.warning(f"雪球指数行情失败: {e}")
        return await get_sina_index_realtime()