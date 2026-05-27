import json
import logging
from pathlib import Path
from typing import Optional
import pandas as pd

logger = logging.getLogger(__name__)

CACHE_FILE = Path(__file__).parent.parent.parent.parent / "data" / "fund_list_cache.json"
_fund_cache: Optional[pd.DataFrame] = None


def _load_cache() -> Optional[pd.DataFrame]:
    global _fund_cache
    if _fund_cache is not None:
        return _fund_cache
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            _fund_cache = pd.DataFrame(data)
            logger.info("fund_cache_loaded records=%d", len(_fund_cache))
            return _fund_cache
        except Exception as e:
            logger.warning("fund_cache_load_failed error=%s", e)
    return None


def _save_cache(df: pd.DataFrame):
    global _fund_cache
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        records = df.to_dict("records")
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        _fund_cache = df
        logger.info("fund_cache_saved records=%d", len(df))
    except Exception as e:
        logger.error("fund_cache_save_failed error=%s", e)


def refresh_fund_cache() -> int:
    import akshare as ak
    try:
        df = ak.fund_name_em()
        if df is None or df.empty:
            logger.warning("fund_name_em returned empty")
            return 0
        required_cols = ["基金代码", "基金简称", "基金类型", "拼音缩写", "拼音全称"]
        for col in required_cols:
            if col not in df.columns:
                logger.error("fund_name_em missing column: %s", col)
                return 0
        _save_cache(df)
        return len(df)
    except Exception as e:
        logger.error("refresh_fund_cache_failed error=%s", e)
        return 0


def search_local(keyword: str, limit: int = 20) -> list[dict]:
    df = _load_cache()
    if df is None:
        return []
    keyword_lower = keyword.lower().strip()
    mask = (
        df["基金代码"].astype(str).str.contains(keyword_lower, case=False, na=False) |
        df["基金简称"].astype(str).str.contains(keyword_lower, case=False, na=False) |
        df["拼音缩写"].astype(str).str.lower().str.contains(keyword_lower, na=False) |
        df["拼音全称"].astype(str).str.lower().str.contains(keyword_lower, na=False)
    )
    matched = df[mask].head(limit)
    results = []
    for _, row in matched.iterrows():
        results.append({
            "fund_code": str(row["基金代码"]).strip().zfill(6),
            "fund_name": str(row["基金简称"]),
            "fund_type_raw": str(row["基金类型"]),
            "pinyin_abbr": str(row.get("拼音缩写", "")),
            "pinyin_full": str(row.get("拼音全称", "")),
        })
    return results


def get_fund_info_local(fund_code: str) -> Optional[dict]:
    df = _load_cache()
    if df is None:
        return None
    code_str = fund_code.strip().zfill(6)
    matched = df[df["基金代码"].astype(str).str.strip().str.zfill(6) == code_str]
    if matched.empty:
        return None
    row = matched.iloc[0]
    return {
        "fund_code": str(row["基金代码"]).strip().zfill(6),
        "fund_name": str(row["基金简称"]),
        "fund_type_raw": str(row["基金类型"]),
        "pinyin_abbr": str(row.get("拼音缩写", "")),
        "pinyin_full": str(row.get("拼音全称", "")),
    }


def ensure_cache_exists() -> bool:
    if _load_cache() is not None:
        return True
    count = refresh_fund_cache()
    return count > 0
