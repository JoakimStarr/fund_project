from pathlib import Path


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

MIN_TRAIN_ROWS = 220
STALE_DAYS = 10
INTERVAL_ALPHA = 0.90


def ensure_dirs() -> None:
    for path in [
        RAW_DIR / "fund_nav",
        RAW_DIR / "index",
        PROCESSED_DIR,
        MODEL_DIR,
        LOG_DIR,
        OUTPUT_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)
