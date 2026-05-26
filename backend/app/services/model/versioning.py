import json
from pathlib import Path
from datetime import datetime
from typing import Optional
import joblib

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
MODEL_DIR = PROJECT_ROOT / "models"


def _get_model_dir(fund_code: str) -> Path:
    d = MODEL_DIR / fund_code
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_model(fund_code: str, model, metrics: dict, features_list: list) -> str:
    model_dir = _get_model_dir(fund_code)
    version = datetime.now().strftime("%Y%m%d")
    model_path = model_dir / f"model_{version}.pkl"
    joblib.dump({"model": model, "metrics": metrics, "features_list": features_list, "saved_at": datetime.now().isoformat()}, model_path)
    versions_path = model_dir / "versions.json"
    versions = []
    if versions_path.exists():
        with open(versions_path) as f:
            versions = json.load(f)
    entry = {"version": version, "saved_at": datetime.now().isoformat(), "metrics": metrics, "features_count": len(features_list), "is_active": True}
    for v in versions:
        v["is_active"] = False
    versions.append(entry)
    keep = 3
    if len(versions) > keep:
        for v in versions[:-keep]:
            old_path = model_dir / f"model_{v['version']}.pkl"
            if old_path.exists():
                old_path.unlink()
        versions = versions[-keep:]
    with open(versions_path, "w") as f:
        json.dump(versions, f, ensure_ascii=False, indent=2)
    latest_path = model_dir / "latest.json"
    with open(latest_path, "w") as f:
        json.dump({"active_version": version, "versions": [v["version"] for v in versions]}, f, ensure_ascii=False)
    return version


def load_model(fund_code: str, version: Optional[str] = None) -> tuple:
    model_dir = _get_model_dir(fund_code)
    if version is None:
        latest_path = model_dir / "latest.json"
        if not latest_path.exists():
            return None, None, None
        with open(latest_path) as f:
            data = json.load(f)
        version = data.get("active_version")
        if not version:
            return None, None, None
    model_path = model_dir / f"model_{version}.pkl"
    if not model_path.exists():
        return None, None, None
    saved = joblib.load(model_path)
    return saved.get("model"), saved.get("metrics"), saved.get("features_list")


def list_versions(fund_code: str) -> list:
    model_dir = _get_model_dir(fund_code)
    versions_path = model_dir / "versions.json"
    if not versions_path.exists():
        return []
    with open(versions_path) as f:
        return json.load(f)


def rollback(fund_code: str, version: str) -> bool:
    model_dir = _get_model_dir(fund_code)
    model_path = model_dir / f"model_{version}.pkl"
    if not model_path.exists():
        return False
    latest_path = model_dir / "latest.json"
    with open(latest_path) as f:
        data = json.load(f)
    data["active_version"] = version
    with open(latest_path, "w") as f:
        json.dump(data, f, ensure_ascii=False)
    versions_path = model_dir / "versions.json"
    if versions_path.exists():
        with open(versions_path) as f:
            versions = json.load(f)
        for v in versions:
            v["is_active"] = v["version"] == version
        with open(versions_path, "w") as f:
            json.dump(versions, f, ensure_ascii=False)
    return True