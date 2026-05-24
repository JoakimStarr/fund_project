# 基金预测系统 — 策略方案实施计划（阶段0 + 阶段1）

> 基于 `fund_nav_prediction_strategy.md` v1.0 · 分析日期：2026-05-24

---

## 目标架构总览

```
用户请求 → 基金画像解析 → 分类路由引擎
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
  偏股流程             债券流程             指数/ETF规则引擎
  (ML全流程)         (物理先验+ML)          (规则优先)
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              ▼
                       模型集成 + 后处理
                    (Conformal Prediction + 约束)
```

---

## 阶段 0：修复 P0 致命问题（立即执行）

### 0.1 修复指数数据 `require_fresh` 不生效

**文件**: `backend/app/services/data_service.py` 第 234 行

**现状**: `get_index_daily()` 在缓存存在且未过期时直接返回缓存，忽略 `require_fresh` 参数。

**修改**: 在缓存检查条件中增加 `not require_fresh`：

```python
# 修改前 (L234)
if cached is not None and not _is_stale(cached):

# 修改后
if cached is not None and not require_fresh and not _is_stale(cached):
```

**验证**: 调用 `load_market_data(require_fresh=True)` 后检查日志中是否出现远端请求而非缓存返回。

---

### 0.2 修复训练/测试集被双重使用

**文件**: `backend/app/services/model_selection_service.py`

**现状**: `_split_train_valid_test()` 划分为 65/17/18，test 集既用于选模（final_metrics）又用于回测。

**修改**:

1. 将 `_split_train_valid_test` 改为四段划分：

```python
def _split_train_valid_test(df):
    n = len(df)
    train_end = int(n * 0.55)
    valid_end = train_end + int(n * 0.22)
    test_sel_end = valid_end + int(n * 0.13)
    return (
        df.iloc[:train_end],
        df.iloc[train_end:valid_end],
        df.iloc[valid_end:test_sel_end],    # test_select：选模用
        df.iloc[test_sel_end:],              # test_final：回测报告用
    )
```

2. 修改 `_point_model` 函数签名和内部逻辑：用 `test_select` 做 final_metrics
3. 修改 `_direction_model` 同样适配
4. 在 `select_and_train` 中，`test_final` 只用于 `_regime_intervals` 和 `backtest` 生成

**验证**: 检查 metrics.json 中的 RMSE/MAE 和 backtest.csv 中的预测值来自不同数据集。

---

### 0.3 修复模型监控文件路径

**文件**: 
- `backend/app/services/model_selection_service.py` 第 813 行
- `backend/app/services/prediction_service.py` 第 475 行

**修改**: 两处 `Path("models")` 改为 `MODEL_DIR`

```python
from app.core.config import MODEL_DIR
monitor_path = MODEL_DIR / fund_code / "t_plus_1_close" / "model_monitoring.json"
```

---

### 0.4 异常HTTP状态码映射

**文件**: `backend/app/core/errors.py`

为每个 AppError 子类添加 `http_status` 属性：

```python
class DataFetchError(AppError):
    code = "DATA_FETCH_FAILED"
    stage = "data_fetch"
    http_status = 502

class DataStaleError(AppError):
    code = "DATA_STALE"
    stage = "data_fetch"
    http_status = 502

class ModelNotFoundError(AppError):
    code = "MODEL_NOT_FOUND"
    stage = "model_registry"
    http_status = 404

class InsufficientDataError(AppError):
    code = "INSUFFICIENT_DATA"
    stage = "data_validation"
    http_status = 422

# 其余保持 400 默认
```

**文件**: `backend/app/main.py`

```python
@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    logger.exception("app_error code=%s", exc.code)
    status = getattr(exc, 'http_status', 400)
    return JSONResponse(status_code=status, content={"ok": False, "error": exc.to_dict(request_id=request_id_var.get())})
```

---

## 阶段 1：基金画像解析与分类路由

### 1.1 新建 `backend/app/services/fund_profile_service.py`

功能：
- 调用 `ak.fund_individual_basic_info_xq` 获取基金基本信息
- 三级分类判断：`基金类型` → `业绩比较基准` → `投资策略`
- 返回标准化的 `FundProfile` 对象

```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class FundProfile:
    fund_code: str
    fund_type: str  # 分类标签
    fund_name: str = ""
    fund_size: Optional[float] = None  # 规模（亿元）
    manager: str = ""
    benchmark: str = ""
    strategy_keywords: list[str] = field(default_factory=list)
    skip_prediction: bool = False  # 货币基金跳过
    raw_info: dict = field(default_factory=dict)

def classify_fund(fund_code: str) -> FundProfile:
    """三级分类判定"""
    try:
        import akshare as ak
        info = ak.fund_individual_basic_info_xq(symbol=fund_code)
    except Exception:
        return FundProfile(fund_code=fund_code, fund_type="hybrid_equity")
    
    # 提取基本信息
    raw_type = str(info.get("基金类型", ""))
    benchmark = str(info.get("业绩比较基准", ""))
    strategy = str(info.get("投资策略", ""))
    fund_name = str(info.get("基金简称", ""))
    
    fund_type = _classify_by_type(raw_type)
    if fund_type == "unknown":
        fund_type = _classify_by_benchmark(benchmark)
    
    size = _parse_size(info.get("最新规模"))
    manager = str(info.get("基金经理", ""))
    keywords = _extract_strategy_keywords(strategy)
    skip = (fund_type == "money_market")
    
    return FundProfile(
        fund_code=fund_code,
        fund_type=fund_type,
        fund_name=fund_name,
        fund_size=size,
        manager=manager,
        benchmark=benchmark,
        strategy_keywords=keywords,
        skip_prediction=skip,
        raw_info=info,
    )

def _classify_by_type(raw_type: str) -> str:
    t = raw_type.lower()
    if "货币" in raw_type:
        return "money_market"
    if "指数" in raw_type or "etf" in t:
        return "index_equity" if "债" not in raw_type else "index_bond"
    if "债券" in raw_type:
        if "可转债" in raw_type: return "bond_convertible"
        if "纯债" in raw_type: return "bond_pure"
        return "bond_mixed"
    if "混合" in raw_type:
        if "偏股" in raw_type: return "hybrid_equity"
        if "偏债" in raw_type: return "hybrid_bond"
        if "平衡" in raw_type: return "hybrid_balanced"
        if "灵活" in raw_type: return "hybrid_flexible"
        return "hybrid_equity"
    if "股票" in raw_type: return "equity_active"
    if "fof" in t or "基金中基金" in raw_type: return "fof"
    if "qdii" in t: return "qdii"
    return "unknown"

def _classify_by_benchmark(benchmark: str) -> str:
    if "沪深300" in benchmark or "中证500" in benchmark:
        return "hybrid_equity"
    if "中债" in benchmark or "国债" in benchmark:
        return "bond_pure"
    return "hybrid_equity"

def _extract_strategy_keywords(strategy: str) -> list[str]:
    kw = []
    for word in ["成长", "价值", "大盘", "小盘", "医药", "科技", "消费", "新能源", "红利"]:
        if word in strategy:
            kw.append(word)
    return kw

def _parse_size(size_str) -> Optional[float]:
    if not size_str:
        return None
    try:
        size_str = str(size_str).replace("亿", "").replace("元", "").strip()
        return float(size_str)
    except (ValueError, TypeError):
        return None
```

---

### 1.2 新建 `backend/app/services/routing_service.py`

```python
"""
分类路由引擎：根据基金类型分发到对应的预测流水线。
阶段1 中，非偏股类型暂时走通用模型，后续阶段逐步实现各类型专用流水线。
"""
from app.services.fund_profile_service import FundProfile
from app.services.prediction_service import predict_next as generic_predict
import logging

logger = logging.getLogger(__name__)

def route_predict(fund_code: str, profile: FundProfile, request_id: str) -> dict:
    """根据基金类型路由到对应预测流水线"""
    
    if profile.skip_prediction:
        return {
            "fund_code": fund_code,
            "fund_type": profile.fund_type,
            "message": "货币基金净值恒为1，无需预测",
            "prediction_mode": "N/A",
            "fund_profile": {
                "type": profile.fund_type,
                "name": profile.fund_name,
                "size": profile.fund_size,
            },
        }
    
    # 阶段1：偏股类走现有成熟流程；其余类型走通用流程（后续阶段逐步替换）
    if profile.fund_type in ("hybrid_equity", "equity_active"):
        logger.info("routing=%s fund_code=%s", profile.fund_type, fund_code)
        result = generic_predict(fund_code, request_id)
    elif profile.fund_type == "index_equity":
        # TODO: 阶段2.3 替换为规则引擎
        logger.info("routing=index_equity (fallback to ML) fund_code=%s", fund_code)
        result = generic_predict(fund_code, request_id)
    elif profile.fund_type == "money_market":
        return {
            "fund_code": fund_code,
            "fund_type": "money_market",
            "message": "货币基金净值恒为1",
        }
    else:
        # 债券、灵活配置、FOF、QDII 暂走通用流程
        logger.info("routing=%s (generic fallback) fund_code=%s", profile.fund_type, fund_code)
        result = generic_predict(fund_code, request_id)
    
    # 附加基金画像信息
    result["fund_profile"] = {
        "type": profile.fund_type,
        "name": profile.fund_name,
        "size": profile.fund_size,
        "manager": profile.manager,
        "benchmark": profile.benchmark,
        "strategy_keywords": profile.strategy_keywords,
    }
    result["fund_type"] = profile.fund_type
    
    return result
```

---

### 1.3 修改 `backend/app/api/fund.py`

在 predict 接口中集成基金画像和路由：

```python
@router.post("/predict")
def predict(req: PredictRequest):
    fund_code = req.fund_code.strip()
    set_log_context(fund_code=fund_code)
    
    # 获取基金画像
    from app.services.fund_profile_service import classify_fund
    profile = classify_fund(fund_code)
    
    # 货币基金直接返回
    if profile.skip_prediction:
        return {"ok": True, "data": {
            "fund_code": fund_code,
            "fund_type": profile.fund_type,
            "message": "货币基金净值恒为1，无需预测",
            "fund_profile": {
                "type": profile.fund_type,
                "name": profile.fund_name,
            },
        }}
    
    # 检查模型
    if not model_exists(fund_code):
        latest_task = get_latest_task(fund_code)
        if latest_task and latest_task.get("status") == "failed":
            raise ModelTrainingFailedError(...)
        raise ModelNotFoundError(...)
    
    # 路由分发
    from app.services.routing_service import route_predict
    data = route_predict(fund_code, profile, request_id_var.get())
    return {"ok": True, "data": data}
```

---

### 1.4 新增 API 端点

**文件**: `backend/app/api/fund.py`

```python
@router.get("/{fund_code}/profile")
def fund_profile(fund_code: str):
    """获取基金画像信息"""
    set_log_context(fund_code=fund_code)
    from app.services.fund_profile_service import classify_fund
    profile = classify_fund(fund_code)
    return {"ok": True, "data": {
        "fund_code": profile.fund_code,
        "fund_type": profile.fund_type,
        "fund_name": profile.fund_name,
        "fund_size": profile.fund_size,
        "manager": profile.manager,
        "benchmark": profile.benchmark,
        "strategy_keywords": profile.strategy_keywords,
        "skip_prediction": profile.skip_prediction,
    }}
```

---

## 实施步骤

| 步骤 | 文件 | 操作 | 说明 |
|------|------|------|------|
| S0.1 | `data_service.py:234` | Edit | 修复 require_fresh |
| S0.2 | `model_selection_service.py` | Edit | 四段数据划分 |
| S0.3 | `model_selection_service.py:813`, `prediction_service.py:475` | Edit | 修复监控路径 |
| S0.4 | `errors.py`, `main.py:36-38` | Edit | HTTP状态码映射 |
| S1.1 | `fund_profile_service.py` | New | 基金画像解析 |
| S1.2 | `routing_service.py` | New | 分类路由引擎 |
| S1.3 | `api/fund.py` | Edit | 集成画像和路由 |
| S1.4 | `api/fund.py` | Edit | 新增 /profile 端点 |

---

## 验证清单

- [ ] `require_fresh=True` 时指数数据走远端
- [ ] backtest.csv 数据来自独立 test_final 集，不参与选模
- [ ] 模型监控文件写入正确绝对路径
- [ ] DataFetchError 返回 502，ModelNotFoundError 返回 404
- [ ] 基金画像正确分类：偏股、债券、指数、货币等
- [ ] 货币基金预测返回 "净值恒为1"
- [ ] 偏股基金走原有 ML 流程不受影响
- [ ] `/api/fund/{code}/profile` 返回正确画像信息
- [ ] 整体功能不受破坏：已有基金 018956 的预测正常

---

## 附：后续阶段概览

| 阶段 | 内容 | 优先级 |
|------|------|--------|
| 阶段 2 | 偏股因子增强 + 因子预筛选(IC/VIF) | P1 |
| 阶段 3 | 债券物理先验因子 + 指数规则引擎 | P1 |
| 阶段 4 | 模型集成(Stacking) + Walk-Forward CV | P1 |
| 阶段 5 | Conformal Prediction + 约束规则 | P1 |
| 阶段 6 | Docker + 测试 + Celery | P2 |