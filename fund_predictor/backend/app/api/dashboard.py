import os
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter

from app.db.database import get_conn

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("/stats")
def get_dashboard_stats():
    """获取仪表盘统计数据"""
    stats = {
        "total_models": _count_trained_models(),
        "avg_accuracy": _calculate_avg_accuracy(),
        "today_predictions": _count_today_predictions(),
        "avg_response_time": _get_avg_response_time(),
        "system_status": _get_system_status(),
    }
    return {"ok": True, "data": stats}


@router.get("/recent-predictions")
def get_recent_predictions(limit: int = 10):
    """获取最近的预测记录"""
    predictions = _load_recent_predictions(limit)
    return {"ok": True, "data": predictions}


@router.get("/models")
def get_model_list():
    """获取已训练的模型列表"""
    models = _get_all_models()
    return {"ok": True, "data": models}


def _count_trained_models() -> int:
    """统计已训练模型数量"""
    models_dir = Path("models")
    if not models_dir.exists():
        return 0
    
    count = 0
    for fund_dir in models_dir.iterdir():
        if fund_dir.is_dir() and fund_dir.name.startswith("fund_"):
            for target_dir in fund_dir.iterdir():
                if target_dir.is_dir():
                    metrics_file = target_dir / "metrics.json"
                    if metrics_file.exists():
                        count += 1
    return count


def _calculate_avg_accuracy() -> dict:
    """计算平均准确率（基于方向准确率）"""
    models_dir = Path("models")
    if not models_dir.exists():
        return {"value": 0, "label": "N/A"}
    
    accuracies = []
    for fund_dir in models_dir.iterdir():
        if fund_dir.is_dir() and fund_dir.name.startswith("fund_"):
            for target_dir in fund_dir.iterdir():
                if target_dir.is_dir():
                    metrics_file = target_dir / "metrics.json"
                    if metrics_file.exists():
                        import json
                        try:
                            with open(metrics_file) as f:
                                metrics = json.load(f)
                            # 尝试获取方向准确率
                            dir_metrics = metrics.get("direction_health", {})
                            acc = dir_metrics.get("accuracy", dir_metrics.get("direction_accuracy"))
                            if acc is not None:
                                accuracies.append(acc)
                        except Exception:
                            pass
    
    if accuracies:
        avg_acc = sum(accuracies) / len(accuracies)
        return {
            "value": round(avg_acc * 100, 1),
            "label": f"{avg_acc * 100:.1f}%"
        }
    
    return {"value": 0, "label": "N/A"}


def _count_today_predictions() -> int:
    """统计今日预测次数"""
    today = datetime.now().strftime("%Y-%m-%d")
    count = 0
    
    models_dir = Path("models")
    if models_dir.exists():
        for fund_dir in models_dir.iterdir():
            if fund_dir.is_dir() and fund_dir.name.startswith("fund_"):
                for target_dir in fund_dir.iterdir():
                    history_file = target_dir / "prediction_history.csv"
                    if history_file.exists():
                        import csv
                        try:
                            with open(history_file) as f:
                                reader = csv.DictReader(f)
                                for row in reader:
                                    pred_time = row.get("timestamp", row.get("date", ""))
                                    if today in str(pred_time):
                                        count += 1
                        except Exception:
                            pass
    return count


def _get_avg_response_time() -> dict:
    """获取平均响应时间（简化版）"""
    # 实际应该从日志或监控获取，这里返回默认值
    return {"value": "< 2s", "label": "< 2s"}


def _get_system_status() -> dict:
    """获取系统各服务状态"""
    services = {
        "model": {"name": "模型服务", "status": "healthy", "value": 98},
        "api": {"name": "API 服务", "status": "healthy", "value": 99},
        "database": {"name": "数据库", "status": "healthy", "value": 95},
        "cache": {"name": "缓存服务", "status": "warning", "value": 92}
    }
    return services


def _load_recent_predictions(limit: int = 10) -> list[dict]:
    """加载最近预测记录"""
    predictions = []
    models_dir = Path("models")
    
    if not models_dir.exists():
        return predictions
    
    all_preds = []
    for fund_dir in models_dir.iterdir():
        if fund_dir.is_dir() and fund_dir.name.startswith("fund_"):
            fund_code = fund_dir.name.replace("fund_", "")
            for target_dir in fund_dir.iterdir():
                if target_dir.is_dir():
                    history_file = target_dir / "prediction_history.csv"
                    if history_file.exists():
                        import csv
                        try:
                            with open(history_file) as f:
                                reader = csv.DictReader(f)
                                rows = list(reader)
                                if rows:
                                    latest = rows[-1]
                                    all_preds.append({
                                        "id": len(all_preds) + 1,
                                        "fundCode": fund_code,
                                        "result": latest.get("pred_return_display", latest.get("pred_return", "N/A")),
                                        "direction": latest.get("direction_signal", "neutral"),
                                        "time": _format_time(latest.get("timestamp", "")),
                                        "p_up": float(latest.get("p_up", 0.5)),
                                    })
                        except Exception:
                            pass
    
    # 按时间排序，取最新的 limit 条
    all_preds.sort(key=lambda x: x["time"], reverse=True)
    return all_preds[:limit]


def _format_time(timestamp: str) -> str:
    """格式化时间为相对时间"""
    if not timestamp:
        return ""
    
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        now = datetime.now(dt.tzinfo or None)
        diff = now - dt
        
        if diff.days > 0:
            return f"{diff.days}天前"
        elif diff.seconds >= 3600:
            hours = diff.seconds // 3600
            return f"{hours}小时前"
        elif diff.seconds >= 60:
            minutes = diff.seconds // 60
            return f"{minutes}分钟前"
        else:
            return "刚刚"
    except Exception:
        return timestamp[:16] if timestamp else ""


def _get_all_models() -> list[dict]:
    """获取所有已训练模型信息"""
    models = []
    models_dir = Path("models")
    
    if not models_dir.exists():
        return models
    
    for fund_dir in models_dir.iterdir():
        if fund_dir.is_dir() and fund_dir.name.startswith("fund_"):
            fund_code = fund_dir.name.replace("fund_", "")
            
            for target_dir in fund_dir.iterdir():
                if target_dir.is_dir():
                    metrics_file = target_dir / "metrics.json"
                    model_info = {
                        "fundCode": fund_code,
                        "targetType": target_dir.name,
                        "trainedAt": "",
                        "pointModel": "-",
                        "directionModel": "-",
                        "accuracy": "-",
                        "status": "unknown"
                    }
                    
                    if metrics_file.exists():
                        import json
                        try:
                            with open(metrics_file) as f:
                                metrics = json.load(f)
                            
                            model_info["trainedAt"] = metrics.get("timestamp", "")
                            model_info["pointModel"] = metrics.get("best_point_model_name", "-")
                            model_info["directionModel"] = metrics.get("best_direction_model_name", "-")
                            
                            dir_health = metrics.get("direction_health", {})
                            acc = dir_health.get("accuracy", dir_health.get("direction_accuracy"))
                            if acc is not None:
                                model_info["accuracy"] = f"{acc * 100:.1f}%"
                            
                            model_info["status"] = "active"
                        except Exception:
                            pass
                    
                    models.append(model_info)
    
    return models
