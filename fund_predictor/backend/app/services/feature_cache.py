import hashlib
import logging
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from app.core.config import PROCESSED_DIR, RAW_DIR
from app.core.logging_config import set_log_context
from app.services.feature_service import build_features

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 86400
_cache_lock = threading.RLock()
_memory_cache: dict[str, tuple[pd.DataFrame, list[str], float]] = {}


def _compute_cache_key(fund_code: str) -> str:
    """
    计算缓存键：fund_code + 数据源文件最后修改时间的hash。

    当源数据更新时，缓存键会自动变化从而失效。
    """
    hasher = hashlib.md5()
    hasher.update(fund_code.encode("utf-8"))

    nav_path = RAW_DIR / "fund_nav" / f"{fund_code}.csv"
    if nav_path.exists():
        mtime = nav_path.stat().st_mtime_ns
        hasher.update(str(mtime).encode())

    for idx_name in ["sh000300", "sz399006", "sh000905", "sh000852", "sh000688"]:
        idx_path = RAW_DIR / "index" / f"{idx_name}.csv"
        if idx_path.exists():
            mtime = idx_path.stat().st_mtime_ns
            hasher.update(str(mtime).encode())

    return f"{fund_code}_{hasher.hexdigest()[:12]}"


def _get_cache_file_path(fund_code: str) -> Path:
    """获取缓存文件的存储路径"""
    return PROCESSED_DIR / f"{fund_code}_features.pkl"


def _save_to_disk(cache_key: str, df: pd.DataFrame, feature_cols: list[str]) -> None:
    """将特征数据持久化到磁盘"""
    try:
        cache_path = _get_cache_file_path(cache_key.split("_")[0])
        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

        data = {
            "cache_key": cache_key,
            "df": df,
            "feature_cols": feature_cols,
            "cached_at": time.time(),
        }
        df.to_pickle(cache_path)

        meta_path = cache_path.with_suffix(".meta.json")
        import json
        with open(meta_path, "w") as f:
            json.dump({
                "cache_key": cache_key,
                "feature_count": len(feature_cols),
                "row_count": len(df),
                "cached_at": datetime.now().isoformat(timespec="seconds"),
                "fund_code": cache_key.split("_")[0],
            }, f)

        logger.info(
            "feature_cache_saved fund=%s path=%s rows=%s features=%s",
            cache_key.split("_")[0], cache_path.name, len(df), len(feature_cols),
        )
    except Exception as e:
        logger.warning("feature_cache_disk_save_failed error=%s", e)


def _load_from_disk(fund_code: str) -> tuple[pd.DataFrame, list[str], str] | None:
    """从磁盘加载缓存数据"""
    cache_path = _get_cache_file_path(fund_code)
    meta_path = cache_path.with_suffix(".meta.json")

    if not cache_path.exists() or not meta_path.exists():
        return None

    try:
        import json
        with open(meta_path) as f:
            meta = json.load(f)

        cached_at_str = meta.get("cached_at")
        if not cached_at_str:
            return None

        cached_at = datetime.fromisoformat(cached_at_str)
        if datetime.now() - cached_at > timedelta(seconds=CACHE_TTL_SECONDS):
            logger.info("feature_cache_expired disk fund=%s age_hours=%.1f",
                       fund_code, (datetime.now() - cached_at).total_seconds() / 3600)
            return None

        df = pd.read_pickle(cache_path)
        stored_key = meta.get("cache_key", "")
        current_key = _compute_cache_key(fund_code)

        if stored_key != current_key:
            logger.info("feature_cache_stale key_mismatch fund=%s stored=%s current=%s",
                        fund_code, stored_key[:20], current_key[:20])
            return None

        feature_cols = []
        sel_path = PROCESSED_DIR / f"{fund_code}_selected_features.json"
        if sel_path.exists():
            with open(sel_path) as f:
                feature_cols = json.load(f)

        logger.info("feature_cache_hit disk fund=%s rows=%s", fund_code, len(df))
        return df, feature_cols, "disk"

    except Exception as e:
        logger.warning("feature_cache_disk_load_failed fund=%s error=%s", fund_code, e)
        return None


def get_cached_features(fund_code: str, force_refresh: bool = False) -> tuple[pd.DataFrame, list[str]]:
    """
    获取带缓存的特征数据。

    缓存策略（三级）：
    1. 内存缓存：最快，同一进程内有效
    2. 磁盘缓存：跨进程/重启后仍可用
    3. 实时计算：缓存全部未命中时重新构建

    缓存键由 fund_code + 源数据文件修改时间hash 组成，
    确保源数据更新时自动失效。
    缓存有效期24小时。

    Args:
        fund_code: 基金代码
        force_refresh: 是否强制刷新（忽略缓存）

    Returns:
        (特征DataFrame, 特征列名列表)
    """
    set_log_context(fund_code=fund_code, stage="feature_cache_check")

    if force_refresh:
        logger.info("feature_cache_force_refresh fund_code=%s", fund_code)
        return _build_and_cache(fund_code)

    cache_key = _compute_cache_key(fund_code)

    with _cache_lock:
        if cache_key in _memory_cache:
            df, cols, ts = _memory_cache[cache_key]
            age = time.time() - ts
            if age < CACHE_TTL_SECONDS:
                logger.info("feature_cache_hit memory fund=%s age=%.0fs", fund_code, age)
                return df.copy(), list(cols)

            del _memory_cache[cache_key]
            logger.info("feature_cache_memory_expired fund=%s", fund_code)

    disk_result = _load_from_disk(fund_code)
    if disk_result is not None:
        df, cols, source = disk_result
        with _cache_lock:
            _memory_cache[cache_key] = (df, cols, time.time())
        return df.copy(), list(cols)

    logger.info("feature_cache_miss fund=%s building_fresh", fund_code)
    return _build_and_cache(fund_code)


def _build_and_cache(fund_code: str) -> tuple[pd.DataFrame, list[str]]:
    """构建特征并写入各级缓存"""
    set_log_context(fund_code=fund_code, stage="feature_cache_build")
    start_time = time.time()

    try:
        df, train_df, meta = build_features(fund_code, require_fresh=True)

        from app.services.feature_service import model_feature_columns
        feature_cols = model_feature_columns(df)

        cache_key = _compute_cache_key(fund_code)
        elapsed = time.time() - start_time

        with _cache_lock:
            _memory_cache[cache_key] = (df, feature_cols, time.time())

        _save_to_disk(cache_key, df, feature_cols)

        set_log_context(stage="feature_cache_build_success")
        logger.info(
            "feature_cache_built fund=%s rows=%s features=%s elapsed=%.2fs",
            fund_code, len(df), len(feature_cols), elapsed,
        )

        return df, feature_cols

    except Exception as e:
        set_log_context(stage="feature_cache_build_failed")
        logger.exception("feature_cache_build_failed fund=%s error=%s", fund_code, e)
        raise


def clear_stale_cache(max_age_hours: int = 26) -> dict:
    """
    清除过期的缓存条目。

    清理范围：
    - 内存缓存中超过 max_age_hours 的条目
    - 磁盘上过期或损坏的 .pkl 文件

    Args:
        max_age_hours: 最大缓存时长（小时），默认26小时（略大于24h TTL）

    Returns:
        清理统计信息字典
    """
    stats = {
        "memory_cleared": 0,
        "disk_cleared": 0,
        "disk_errors": 0,
        "total_inspected": 0,
    }

    now = time.time()

    with _cache_lock:
        expired_keys = [
            k for k, (_, _, ts) in _memory_cache.items()
            if now - ts > max_age_hours * 3600
        ]
        for k in expired_keys:
            del _memory_cache[k]
            stats["memory_cleared"] += 1

    if PROCESSED_DIR.exists():
        for pkl_file in PROCESSED_DIR.glob("*_features.pkl"):
            stats["total_inspected"] += 1
            try:
                mtime = pkl_file.stat().st_mtime
                age_hours = (now - mtime) / 3600

                if age_hours > max_age_hours:
                    pkl_file.unlink(missing_ok=False)
                    meta_file = pkl_file.with_suffix(".meta.json")
                    if meta_file.exists():
                        meta_file.unlink(missing_ok=False)
                    stats["disk_cleared"] += 1
                    logger.info("feature_cache_cleaned file=%s age=%.1fh", pkl_file.name, age_hours)
            except Exception as e:
                stats["disk_errors"] += 1
                logger.warning("feature_cache_cleanup_error file=%s error=%s", pkl_file.name, e)

    logger.info(
        "feature_cache_cleanup_complete memory=%s disk=%s errors=%s total=%s",
        stats["memory_cleared"], stats["disk_cleared"], stats["disk_errors"],
        stats["total_inspected"],
    )
    return stats


def invalidate_cache(fund_code: str | None = None) -> int:
    """
    使缓存失效。

    Args:
        fund_code: 指定基金代码使单个缓存失效；None则清除所有内存缓存

    Returns:
        清除的缓存条目数
    """
    count = 0
    with _cache_lock:
        if fund_code:
            keys_to_remove = [k for k in _memory_cache if k.startswith(fund_code)]
            for k in keys_to_remove:
                del _memory_cache[k]
                count += 1
        else:
            count = len(_memory_cache)
            _memory_cache.clear()

    if fund_code:
        cache_path = _get_cache_file_path(fund_code)
        if cache_path.exists():
            try:
                cache_path.unlink(missing_ok=False)
                meta_path = cache_path.with_suffix(".meta.json")
                if meta_path.exists():
                    meta_path.unlink(missing_ok=False)
                count += 1
            except Exception as e:
                logger.warning("feature_cache_invalidate_disk_error fund=%s error=%s", fund_code, e)

    logger.info("feature_cache_invalidated fund=%s cleared=%s", fund_code or "*", count)
    return count
