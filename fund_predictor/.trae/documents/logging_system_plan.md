# 工程级日志系统实施方案

> 目标：从服务启动到前端每一次点击和API调用，全链路可追踪、可检索、可分析。
> 状态：**已批准，待实施**

---

## 实施步骤总览（12个文件）

### Step 1: 扩展 config.yaml 日志段
- **文件**: `config.yaml` — 在现有 `logging:` 段（仅3行）基础上扩展为完整配置（~80行）
- **内容**: 6个日志handler配置 + 控制台/文件通用设置 + 第三方库级别 + 采样策略 + 脱敏设置

### Step 2: 重写后端日志核心系统
- **文件**: `backend/app/core/logging_config.py`
- **改造点**:
  - 从 config.yaml 驱动全部配置（不再硬编码）
  - 新增 `StructuredJSONHandler` 类（输出 JSONL 格式，适合 ELK 采集）
  - 新增 api_logger / audit_logger / perf_logger 专用 logger
  - 新增 `audit_log()` 工具函数
  - 新增 `log_performance()` 装饰器
  - 第三方库日志级别独立控制

### Step 3: 增强 FastAPI 中间件
- **文件**: `backend/app/main.py`
- **改造点**:
  - request_context 中间件增加耗时统计
  - 响应头增加 `X-Response-Time-ms`
  - 每次请求记录到 api.jsonl（结构化）
  - 异常请求也记录耗时

### Step 4: 新建性能日志模块
- **新建**: `backend/app/core/perf_logger.py`
- **内容**: `log_performance` 装饰器 + `record_performance` 函数式调用

### Step 5: 新建审计日志模块
- **新建**: `backend/app/core/audit_logger.py`
- **内容**: `audit_log(action, target, details)` 函数

### Step 6: 前端结构化日志系统
- **新建**: `frontend/src/utils/logger.js`
- **功能**: 多级别(debug/info/warn/error) + 内存缓冲 + 控制台输出 + 页面性能采集 + 用户操作审计 + 远程上报(可选)

### Step 7: 前端 API 请求注入日志
- **修改**: `frontend/src/utils/request.js`
- **改造点**: 在 axios 拦截器中注入 logger 调用（请求发出/响应接收/错误 各阶段）

### Step 8: Vue 全局错误边界
- **修改**: `frontend/src/App.vue`
- **改造点**: 添加 `onErrorCaptured` 钩子捕获组件渲染错误并记录日志

### Step 9: Vite 错误捕获插件
- **修改**: `frontend/vite.config.js`
- **改造点**: 自定义 Vite 插件捕获 dev server HTTP 错误和慢请求

### Step 10: NPM 启动日志脚本
- **新建**: `frontend/scripts/log-start.js`
- **功能**: 记录前端启动/关闭生命周期事件到 `logs/frontend/dev.log`

### Step 11: 更新 package.json scripts
- **修改**: `frontend/package.json`
- **改造点**: dev/dev:all/build 脚本前插入 log-start.js

### Step 12: 日志系统测试 + Docker 配置检查
- **新建**: `tests/test_logging.py`
- **检查**: docker-compose.yml logs 目录挂载

---

## 文件变更矩阵

| # | 操作 | 文件路径 | 改动量 |
|---|------|----------|--------|
| 1 | 修改 | `config.yaml` | +75行 (logging段扩展) |
| 2 | 重写 | `backend/app/core/logging_config.py` | ~200行 (完全重写) |
| 3 | 修改 | `backend/app/main.py` | +25行 (中间件增强) |
| 4 | 新建 | `backend/app/core/perf_logger.py` | ~40行 |
| 5 | 新建 | `backend/app/core/audit_logger.py` | ~35行 |
| 6 | 新建 | `frontend/src/utils/logger.js` | ~120行 |
| 7 | 修改 | `frontend/src/utils/request.js` | +15行 (注入logger) |
| 8 | 修改 | `frontend/src/App.vue` | +10行 (错误边界) |
| 9 | 修改 | `frontend/vite.config.js` | +25行 (错误插件) |
| 10 | 新建 | `frontend/scripts/log-start.js` | ~40行 |
| 11 | 修改 | `frontend/package.json` | +3行 (scripts) |
| 12 | 新建 | `tests/test_logging.py` | ~80行 |

---

## 日志产出物（运行后自动生成）

```
logs/
├── app.log              # 应用主日志 (文本+上下文)
├── api.jsonl            # API访问日志 (JSON结构化)
├── train.log             # 训练任务日志
├── error.log             # 错误日志 (ERROR+)
├── audit.jsonl           # 审计操作日志 (JSON)
├── perf.jsonl            # 性能指标日志 (JSON)
└── frontend/
    ├── app.log           # 前端应用日志
    ├── error.log         # 前端错误日志
    └── dev.log           # NPM/Vite 启动日志
```

---

## 验证清单

- [ ] `config.yaml` 的 logging 段被代码正确读取
- [ ] `logs/` 目录下生成全部6种后端日志文件
- [ ] `app.log` 含 request_id/fund_code/stage 上下文
- [ ] `api.jsonl` 每行为有效 JSON
- [ ] `perf.jsonl` 记录关键操作耗时
- [ ] `audit.jsonl` 记录用户操作
- [ ] 前端 console 输出带 `[LEVEL] [module]` 前缀
- [ ] 前端 `logs/frontend/dev.log` 记录启动信息
- [ ] API 响应头包含 X-Response-Time-ms
- [ ] 第三方库日志降至 WARNING
- [ ] 原有 26 个测试不受影响
- [ ] Docker compose logs 目录挂载正确
