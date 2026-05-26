from pathlib import Path

import yaml

ROOT_DIR = Path(__file__).resolve().parents[3]
STATIC_DIR = ROOT_DIR / "static"
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
MODEL_DIR = ROOT_DIR / "models"
LOG_DIR = ROOT_DIR / "logs"
OUTPUT_DIR = ROOT_DIR / "output"
DB_PATH = ROOT_DIR / "output" / "app.db"

INDEX_SYMBOLS = {
    "hs300": "sh000300",
    "zz500": "sh000905",
    "zz1000": "sh000852",
    "cyb": "sz399006",
    "kcb50": "sh000688",
}

_CONFIG_PATH = ROOT_DIR / "config.yaml"


def _load_yaml_config() -> dict:
    if _CONFIG_PATH.exists():
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


_cfg = _load_yaml_config()

MIN_TRAIN_ROWS = int(_cfg.get("data", {}).get("min_train_rows", 220))
STALE_DAYS = int(_cfg.get("data", {}).get("cache_stale_days", 10))
INTERVAL_ALPHA = float(_cfg.get("interval", {}).get("default_alpha", 0.90))

FETCH_TIMEOUT = int(_cfg.get("data", {}).get("fetch_timeout_seconds", 20))
FETCH_MAX_WORKERS = int(_cfg.get("data", {}).get("fetch_max_workers", 5))

TRAIN_SPLIT_RATIO = _cfg.get("model", {}).get("train_split_ratio", [0.55, 0.22, 0.13, 0.10])
SAMPLE_WEIGHT_HALFLIFE = int(_cfg.get("model", {}).get("sample_weight_halflife", 60))

RIDGE_ALPHA = float(_cfg.get("model", {}).get("ridge_alpha", 1.0))
N_ESTIMATORS = int(_cfg.get("model", {}).get("n_estimators", 120))
MAX_DEPTH = int(_cfg.get("model", {}).get("max_depth", 5))
LEARNING_RATE = float(_cfg.get("model", {}).get("learning_rate", 0.05))

# GPU配置
USE_GPU = bool(_cfg.get("model", {}).get("use_gpu", False))
GPU_DEVICE = str(_cfg.get("model", {}).get("gpu_device", "cuda:0"))
GPU_MIN_SAMPLES = int(_cfg.get("model", {}).get("gpu_min_samples", 10000))


def get_gpu_params(n_samples: int) -> dict:
    """根据样本数和配置返回GPU参数
    
    Args:
        n_samples: 训练样本数
        
    Returns:
        GPU参数字典，可用于XGBoost/LightGBM
    """
    if not USE_GPU or n_samples < GPU_MIN_SAMPLES:
        return {"tree_method": "hist", "device": "cpu"}
    
    return {
        "tree_method": "hist",
        "device": GPU_DEVICE,
    }

BOND_DURATION_ESTIMATE = _cfg.get("bond", {}).get("duration_estimate", {})
DAILY_FEE = float(_cfg.get("bond", {}).get("daily_fee", 0.000003))

NAV_LIMITS = {k: v for k, v in _cfg.get("nav_constraints", {}).items() if isinstance(v, (int, float))}

IC_THRESHOLD = float(_cfg.get("screening", {}).get("ic_threshold", 0.02))
VIF_THRESHOLD = float(_cfg.get("screening", {}).get("vif_threshold", 10.0))

# 数据源配置（优先级：雪球 > 新浪 > 东财 > 搜狐 > 缓存）
DATA_SOURCE_PRIORITY = {
    "fund_nav": ["xueqiu", "sina", "eastmoney", "cache"],
    "index_data": ["sina", "tencent", "eastmoney", "sohu", "cache"]
}

# 数据源启用状态
DATA_SOURCE_ENABLED = _cfg.get("data_sources", {}).get("enabled", {
    "xueqiu": True,
    "sina": True,
    "tencent": True,
    "eastmoney": True,
    "sohu": True
})

# 请求间隔控制（秒）- 避免被封
REQUEST_INTERVAL = _cfg.get("data_sources", {}).get("request_interval", {
    "xueqiu": 2.0,
    "sina": 1.5,
    "tencent": 1.5,
    "eastmoney": 2.0,
    "sohu": 2.5
})

# 最大重试次数和间隔
MAX_RETRY_TIMES = int(_cfg.get("data_sources", {}).get("max_retry_times", 3))
RETRY_INTERVAL = float(_cfg.get("data_sources", {}).get("retry_interval", 1.0))


def ensure_dirs() -> None:
    for path in [
        RAW_DIR / "fund_nav",
        RAW_DIR / "index",
        RAW_DIR / "stocks",
        RAW_DIR / "theme_index",
        RAW_DIR / "holdings",
        PROCESSED_DIR,
        MODEL_DIR,
        LOG_DIR,
        OUTPUT_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)