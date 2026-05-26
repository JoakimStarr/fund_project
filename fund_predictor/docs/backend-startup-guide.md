# 后端服务启动指南

## ⚠️ 重要：必须使用正确的 Python 环境

### 问题现象
如果看到以下日志，说明使用了**错误的 Python 环境**：
```
File "/home/joakim/miniconda3/lib/python3.13/site-packages/..."
[WARNING] lightgbm_not_available
[WARNING] xgboost_not_available
```

### ✅ 正确的启动方式

#### 方法 1：使用 start.sh（推荐）
```bash
cd /home/joakim/Project/fund_project/fund_predictor
./start.sh
```

**优点**：
- 自动使用 `.venv` 虚拟环境（包含 lightgbm/xgboost 等依赖）
- 自动安装依赖
- 自动检测端口占用
- 启动后自动打开浏览器

#### 方法 2：手动启动（必须激活虚拟环境）
```bash
cd /home/joakim/Project/fund_project/fund_predictor

# 激活虚拟环境
source .venv/bin/activate

# 验证 Python 环境（应该显示 .venv 路径）
which python
# 输出: /home/joakim/Project/fund_project/fund_predictor/.venv/bin/python

# 验证 LightGBM 已安装
python -c "import lightgbm; print('LightGBM:', lightgbm.__version__)"

# 启动后端
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

### ❌ 错误的启动方式（会导致依赖缺失）

#### 错误示例 1：直接使用系统 Python
```bash
# ❌ 不要这样做！
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
**问题**：可能使用 `/usr/bin/python` 或 `miniconda3` 的 Python，缺少项目依赖

#### 错误示例 2：在 miniconda3 基础环境中启动
```bash
# ❌ 如果当前在 (base) conda 环境中
conda deactivate  # 先退出 base 环境
source .venv/bin/activate  # 再激活项目虚拟环境
```

---

## 📋 依赖检查清单

启动前请确认以下包已安装在 **`.venv`** 环境中：

```bash
source .venv/bin/activate

# 必需依赖
pip list | grep -E "(lightgbm|xgboost|fastapi|pandas|scikit-learn|akshare)"

# 预期输出：
# lightgbm               4.6.0        ✅
# xgboost                2.x.x         ✅
# fastapi                0.104.x       ✅
# pandas                 2.x.x         ✅
# scikit-learn           1.3.x         ✅
# akshare                1.10.x        ✅
```

如果缺少依赖：
```bash
pip install -r backend/requirements.txt
```

---

## 🔧 Intraday API 使用说明

### 改进后的行为（v2.7.2+）

#### GET /api/v1/fund/{fund_code}/intraday/latest

**新增参数**：
- `auto_estimate` (bool, 默认 `true`) - 缓存为空时是否自动触发估算

**优先级逻辑**：
1. `force_refresh=true` → 强制重新计算
2. 缓存命中 → 直接返回缓存数据
3. **缓存未命中 + auto_estimate=true** → **自动触发估算并返回** ✨ 新功能！
4. 缓存未命中 + auto_estimate=false → 返回 404 提示手动调用 POST

**示例请求**：

```bash
# 场景 1：正常访问（推荐）- 自动处理缓存未命中
curl http://localhost:8000/api/v1/fund/018956/intraday/latest
# 返回：200 OK + 估算数据（如果缓存为空会自动计算）

# 场景 2：禁用自动估算（传统模式）
curl "http://localhost:8000/api/v1/fund/018956/intraday/latest?auto_estimate=false"
# 返回：404 Not Found （如果缓存为空）

# 场景 3：强制刷新
curl "http://localhost:8000/api/v1/fund/018956/intraday/latest?force_refresh=true"
# 返回：200 OK + 最新计算结果

# 场景 4：手动触发估算（POST 接口仍然可用）
curl -X POST http://localhost:8000/api/v1/fund/018956/intraday
# 返回：200 OK + 完整估算结果
```

**响应格式**：

```json
{
  "ok": true,
  "data": {
    "fund_code": "018956",
    "last_nav": 1.2345,
    "last_date": "2026-05-23",
    "estimated_nav": 1.2456,
    "estimated_change_pct": 0.0899,
    "holding_path_return": 0.001,
    "index_path_return": 0.0008,
    "fusion_weight": {"path_a": 0.6, "path_b": 0.4},
    "confidence": 0.75,
    "from_cache": false,
    "auto_triggered": true,  // ← 标识这是自动触发的估算
    "estimated_at": "2026-05-26T13:50:00"
  }
}
```

---

## 🚨 故障排查

### 问题 1: lightgbm_not_available 警告

**症状**：
```
[WARNING] lightgbm_not_available
```

**原因**：使用了错误的 Python 环境

**解决方案**：
```bash
# 检查当前 Python
which python

# 如果不是 .venv/bin/python，重新启动：
pkill -f uvicorn
./start.sh  # 或者手动激活 .venv 后再启动
```

### 问题 2: Intraday 返回 500 错误

**症状**：
```
IntradayEstimateError: 盘中估算失败: 无法获取基金净值数据
```

**原因**：
- 基金代码无效
- 数据源不可用（网络问题、AKShare 接口变更）
- 缺少必要的市场数据文件

**解决方案**：
1. 检查基金代码是否正确（6位数字）
2. 检查网络连接
3. 查看 `logs/error.log` 详细错误信息

### 问题 3: Intraday 估算结果不准确

**症状**：估算值与实际净值偏差较大

**可能原因**：
- 持仓数据过期（季报延迟）
- 市场异常波动
- 双路径融合权重不合理

**优化建议**：
- 使用 `force_refresh=true` 强制重新计算
- 检查持仓数据的时效性
- 调整 `REGRESSION_WINDOW` 和 `FUSION_WINDOW` 参数

---

## 📊 性能优化建议

### Intraday 缓存策略

当前实现使用**内存缓存**（`_intraday_cache` 字典），特点：

| 特性 | 说明 |
|------|------|
| **优点** | 响应速度快（<1ms） |
| **缺点** | 服务重启后丢失 |
| **适用场景** | 开发/测试环境 |

**生产环境建议**（可选升级）：

#### 方案 A: SQLite 持久化缓存
```python
import sqlite3
from datetime import datetime, timedelta

def save_intraday_to_db(fund_code: str, result: dict):
    conn = sqlite3.connect("output/app.db")
    conn.execute("""
        INSERT OR REPLACE INTO intraday_cache
        (fund_code, estimated_nav, estimated_change_pct, created_at)
        VALUES (?, ?, ?, ?)
    """, (fund_code, result["estimated_nav"], result["estimated_change_pct"], datetime.now()))
    conn.commit()
    conn.close()

def get_intraday_from_db(fund_code: str) -> dict | None:
    conn = sqlite3.connect("output/app.db")
    row = conn.execute("""
        SELECT * FROM intraday_cache
        WHERE fund_code = ? AND created_at > ?
        ORDER BY created_at DESC LIMIT 1
    """, (fund_code, datetime.now() - timedelta(hours=24))).fetchone()
    conn.close()
    return dict(row) if row else None
```

#### 方案 B: Redis 分布式缓存（高并发场景）
```python
import redis

r = redis.Redis(host='localhost', port=6379, db=0)

def cache_intraday(fund_code: str, result: dict, ttl: int = 300):
    r.setex(f"intraday:{fund_code}", ttl, json.dumps(result))

def get_cached_intraday(fund_code: str) -> dict | None:
    data = r.get(f"intraday:{fund_code}")
    return json.loads(data) if data else None
```

---

## 🎯 最佳实践

1. **开发环境**：使用 `--reload` 参数启用热重载
   ```bash
   python -m uvicorn app.main:app --app-dir backend --reload
   ```

2. **生产环境**：使用 Gunicorn + Uvicorn workers
   ```bash
   gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
   ```

3. **Docker 部署**：使用 docker-compose
   ```bash
   docker-compose up -d backend
   ```

4. **监控日志**：
   ```bash
   tail -f logs/app.log logs/error.log
   ```

---

## 📝 更新历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v2.7.2 | 2026-05-26 | 新增 Intraday 自动估算功能 |
| v2.7.1 | 2026-05-26 | 修复 LightGBM 依赖缺失 |
| v2.7.0 | 2026-05-26 | Model-Monitor 数据真实性修复 |

---

**维护者**: AI Assistant
**最后更新**: 2026-05-26 13:50 CST
