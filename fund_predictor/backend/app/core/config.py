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

BOND_DURATION_ESTIMATE = _cfg.get("bond", {}).get("duration_estimate", {})
DAILY_FEE = float(_cfg.get("bond", {}).get("daily_fee", 0.000003))

NAV_LIMITS = {k: v for k, v in _cfg.get("nav_constraints", {}).items() if isinstance(v, (int, float))}

IC_THRESHOLD = float(_cfg.get("screening", {}).get("ic_threshold", 0.02))
VIF_THRESHOLD = float(_cfg.get("screening", {}).get("vif_threshold", 10.0))


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