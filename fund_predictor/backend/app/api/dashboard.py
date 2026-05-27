import os
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter

from app.db.database import get_conn

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


def _extract_fund_code(dir_name: str) -> str | None:
    """
    从目录名提取基金代码
    支持两种格式：
    - fund_000001 (旧格式，带fund_前缀)
    - 000001 (新格式，直接是6位数字)
    """
    if dir_name.startswith("fund_"):
        code = dir_name[5:]
        if code.isdigit() and len(code) == 6:
            return code
    elif dir_name.isdigit() and len(dir_name) == 6:
        return dir_name
    return None


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


@router.get("/system-resources")
def get_system_resources():
    """获取系统资源使用情况（CPU、内存、磁盘）"""
    import shutil

    resources = {}

    # 磁盘空间
    try:
        total, used, free = shutil.disk_usage("/")
        resources["disk"] = {
            "total_gb": round(total / (1024**3), 1),
            "used_gb": round(used / (1024**3), 1),
            "free_gb": round(free / (1024**3), 1),
            "usage_percent": round((used / total) * 100, 1)
        }
    except Exception as e:
        resources["disk"] = {"error": str(e)}

    # 内存使用（Linux）
    try:
        with open('/proc/meminfo', 'r') as f:
            meminfo = f.read()
        mem_data = {}
        for line in meminfo.split('\n'):
            if ':' in line:
                key, val = line.split(':')
                mem_data[key.strip()] = int(val.strip().split()[0])  # KB
        total_mem = mem_data.get('MemTotal', 0)
        available_mem = mem_data.get('MemAvailable', mem_data.get('MemFree', 0))
        used_mem = total_mem - available_mem
        resources["memory"] = {
            "total_mb": round(total_mem / 1024, 0),
            "used_mb": round(used_mem / 1024, 0),
            "free_mb": round(available_mem / 1024, 0),
            "usage_percent": round((used_mem / total_mem * 100), 1) if total_mem > 0 else 0
        }
    except Exception as e:
        resources["memory"] = {"error": str(e)}

    # CPU信息（简化版，不使用psutil）
    try:
        import time
        with open('/proc/stat', 'r') as f:
            line = f.readline()
            cpu_times = list(map(int, line.split()[1:]))
        time.sleep(0.1)
        with open('/proc/stat', 'r') as f:
            line = f.readline()
            cpu_times2 = list(map(int, line.split()[1:]))

        delta = [t2 - t1 for t1, t2 in zip(cpu_times, cpu_times2)]
        total_delta = sum(delta)
        if total_delta > 0:
            idle_delta = delta[3]
            cpu_usage = round((1 - idle_delta / total_delta) * 100, 1)
        else:
            cpu_usage = 0

        resources["cpu"] = {
            "usage_percent": cpu_usage,
            "cores": os.cpu_count() or 0
        }
    except Exception as e:
        resources["cpu"] = {"error": str(e)}

    return {"ok": True, "data": resources}


def _count_trained_models() -> int:
    """统计已训练模型数量"""
    models_dir = Path("models")
    if not models_dir.exists():
        return 0
    
    count = 0
    for fund_dir in models_dir.iterdir():
        if fund_dir.is_dir() and _extract_fund_code(fund_dir.name):
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
        if fund_dir.is_dir() and _extract_fund_code(fund_dir.name):
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
            if fund_dir.is_dir() and _extract_fund_code(fund_dir.name):
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
    """获取平均响应时间（基于数据库查询性能）"""
    try:
        import time
        from app.db.database import get_conn

        start = time.time()
        with get_conn() as conn:
            conn.execute("SELECT COUNT(*) FROM train_results").fetchone()
        elapsed_ms = (time.time() - start) * 1000

        if elapsed_ms < 50:
            return {"value": f"{elapsed_ms:.0f}ms", "label": "< 50ms"}
        elif elapsed_ms < 200:
            return {"value": f"{elapsed_ms:.0f}ms", "label": "< 200ms"}
        else:
            return {"value": f"{elapsed_ms:.0f}ms", "label": f"~{elapsed_ms:.0f}ms"}
    except Exception:
        return {"value": "N/A", "label": "无法检测"}


def _get_system_status() -> dict:
    """获取系统各服务状态（基于真实检测）"""
    import time
    import shutil

    services = {}

    # 检测模型服务状态（检查models目录是否存在且可访问）
    try:
        models_dir = Path("models")
        start = time.time()
        if models_dir.exists():
            model_count = len([d for d in models_dir.iterdir()
                               if d.is_dir() and _extract_fund_code(d.name)
                               for _ in d.glob("**/metrics.json")])
            elapsed = (time.time() - start) * 1000
            health = min(99, max(60, 100 - elapsed / 10))
            services["model"] = {
                "name": "模型服务",
                "status": "healthy" if health >= 80 else "warning",
                "value": round(health)
            }
        else:
            services["model"] = {
                "name": "模型服务",
                "status": "error",
                "value": 0
            }
    except Exception as e:
        services["model"] = {"name": "模型服务", "status": "error", "value": 0}

    # 检测API服务（当前能响应说明API正常）
    services["api"] = {
        "name": "API 服务",
        "status": "healthy",
        "value": 100
    }

    # 检测数据库状态（尝试查询）
    try:
        from app.db.database import get_conn
        start = time.time()
        with get_conn() as conn:
            conn.execute("SELECT 1").fetchone()
        elapsed = (time.time() - start) * 1000
        health = min(99, max(70, 100 - elapsed / 5))
        services["database"] = {
            "name": "数据库",
            "status": "healthy" if health >= 80 else "warning",
            "value": round(health)
        }
    except Exception:
        services["database"] = {"name": "数据库", "status": "error", "value": 0}

    # 检测磁盘空间
    try:
        total, used, free = shutil.disk_usage("/")
        usage_pct = (used / total) * 100
        if usage_pct > 90:
            status = "error"
        elif usage_pct > 75:
            status = "warning"
        else:
            status = "healthy"
        services["cache"] = {
            "name": "存储空间",
            "status": status,
            "value": round(100 - usage_pct, 1)
        }
    except Exception:
        services["cache"] = {"name": "存储空间", "status": "unknown", "value": 0}

    return services


def _load_recent_predictions(limit: int = 10) -> list[dict]:
    """加载最近预测记录"""
    predictions = []
    models_dir = Path("models")
    
    if not models_dir.exists():
        return predictions
    
    all_preds = []
    for fund_dir in models_dir.iterdir():
        fund_code = _extract_fund_code(fund_dir.name)
        if fund_dir.is_dir() and fund_code:
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
    """获取所有已训练模型信息（从文件系统和数据库）"""
    models = []
    models_dir = Path("models")

    if not models_dir.exists():
        return models

    # 从数据库预加载基金名称
    fund_names = {}
    try:
        from app.db.database import get_conn
        with get_conn() as conn:
            rows = conn.execute("SELECT fund_code, fund_name FROM fund_profiles").fetchall()
            for row in rows:
                fund_names[row["fund_code"]] = row["fund_name"]
    except Exception:
        pass

    for fund_dir in models_dir.iterdir():
        fund_code = _extract_fund_code(fund_dir.name)
        if fund_dir.is_dir() and fund_code:

            # 检查是否有子目录（新格式）或直接在根目录（旧格式）
            has_subdirs = any(d.is_dir() for d in fund_dir.iterdir() if not d.name.startswith('.'))

            if has_subdirs:
                for target_dir in fund_dir.iterdir():
                    if target_dir.is_dir():
                        metrics_file = target_dir / "metrics.json"
                        model_info = {
                            "fundCode": fund_code,
                            "fundName": fund_names.get(fund_code, f"基金 {fund_code}"),
                            "targetType": target_dir.name,
                            "trainedAt": "",
                            "modelVersion": "",
                            "pointModel": "-",
                            "directionModel": "-",
                            "accuracy": 0,
                            "predictions": 0,
                            "status": "unknown"
                        }

                        # 统计预测次数
                        history_file = target_dir / "prediction_history.csv"
                        if history_file.exists():
                            try:
                                import csv
                                with open(history_file) as f:
                                    reader = csv.DictReader(f)
                                    model_info["predictions"] = sum(1 for _ in reader)
                            except Exception:
                                pass

                        if metrics_file.exists():
                            import json
                            try:
                                with open(metrics_file) as f:
                                    metrics = json.load(f)

                                # 获取训练时间（支持多种字段名）
                                model_info["trainedAt"] = metrics.get("timestamp", "")

                                # 支持新旧两种metrics格式
                                # 新格式: { point: {...}, direction: {...} }
                                # 旧格式: { direction_health: {...}, best_xxx_model_name: ... }

                                if "direction" in metrics:
                                    direction = metrics["direction"]
                                    acc = direction.get("direction_acc_03", direction.get("direction_acc"))
                                    if acc is not None:
                                        model_info["accuracy"] = round(acc * 100, 1)
                                    model_info["status"] = "active" if direction.get("direction_available") else "unknown"

                                    # 使用prediction_mode作为版本信息
                                    pred_mode = metrics.get("prediction_mode", "")
                                    training_mode = metrics.get("training_mode", "")
                                    if pred_mode or training_mode:
                                        model_info["modelVersion"] = f"{pred_mode} ({training_mode})"
                                else:
                                    # 旧格式兼容
                                    model_info["pointModel"] = metrics.get("best_point_model_name", "-")
                                    model_info["directionModel"] = metrics.get("best_direction_model_name", "-")

                                    point_model = metrics.get("best_point_model_name", "")
                                    direction_model = metrics.get("best_direction_model_name", "")
                                    if direction_model:
                                        model_info["modelVersion"] = direction_model.split("_v")[-1] if "_v" in direction_model else "v1.0"
                                    elif point_model:
                                        model_info["modelVersion"] = point_model.split("_v")[-1] if "_v" in point_model else "v1.0"

                                    dir_health = metrics.get("direction_health", {})
                                    acc = dir_health.get("accuracy", dir_health.get("direction_accuracy"))
                                    if acc is not None:
                                        model_info["accuracy"] = round(acc * 100, 1)

                                    model_info["status"] = "active"
                            except Exception:
                                pass

                        models.append(model_info)
            else:
                # 旧格式：metrics.json直接在基金目录根下
                metrics_file = fund_dir / "metrics.json"
                if metrics_file.exists():
                    model_info = {
                        "fundCode": fund_code,
                        "fundName": fund_names.get(fund_code, f"基金 {fund_code}"),
                        "targetType": "legacy",
                        "trainedAt": "",
                        "modelVersion": "v1.0 (legacy)",
                        "pointModel": "-",
                        "directionModel": "-",
                        "accuracy": 0,
                        "predictions": 0,
                        "status": "unknown"
                    }

                    # 统计预测次数
                    history_file = fund_dir / "prediction_history.csv"
                    if history_file.exists():
                        try:
                            import csv
                            with open(history_file) as f:
                                reader = csv.DictReader(f)
                                model_info["predictions"] = sum(1 for _ in reader)
                        except Exception:
                            pass

                    try:
                        import json
                        with open(metrics_file) as f:
                            metrics = json.load(f)

                        model_info["trainedAt"] = metrics.get("timestamp", "")

                        # 旧格式使用 direction_acc_03 或 direction_health
                        acc = metrics.get("direction_acc_03")
                        if acc is None:
                            dir_health = metrics.get("direction_health", {})
                            acc = dir_health.get("accuracy", dir_health.get("direction_accuracy"))
                        if acc is not None:
                            model_info["accuracy"] = round(acc * 100, 1)

                        model_info["status"] = "active"
                    except Exception:
                        pass

                    models.append(model_info)

    return models
