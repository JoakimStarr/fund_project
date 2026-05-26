# 修复多个页面数据显示问题 Spec

## Why
用户报告了5个关键页面的问题：
1. Intraday 页面报错：`cannot import name 'NotFoundError' from 'app.core.errors'`
2. Backtest 页面选择基金后没有数据显示（即使存在回测数据）
3. Model-Monitor 数据显示不真实、不完善
4. Profile 页面输入基金代码后所有字段都为空（基金名称、成立日期、规模等）
5. Train 页面历史训练记录缺少任务ID和基金代码列

这些问题严重影响用户体验，需要立即修复。

## What Changes
- **修复 NotFoundError 导入错误**：在 `errors.py` 中添加 `NotFoundError` 类
- **修复 Profile 数据获取**：优化 `fund_profile_service.py` 的 `classify_fund()` 函数，增强数据获取逻辑
- **修复 Backtest 数据显示**：检查并修复 backtest API 数据返回格式
- **修复 Model-Monitor 数据**：更新模型监控 API，返回真实的模型状态数据
- **修复 Train 任务列表**：确保 tasks API 返回完整的任务信息（包含 task_id, fund_code）

## Impact
- Affected specs: 无（纯 bugfix）
- Affected code:
  - `backend/app/core/errors.py` - 添加 NotFoundError 类
  - `backend/app/api/intraday.py` - 修复导入错误
  - `backend/app/services/fund_profile_service.py` - 增强数据获取
  - `backend/app/api/fund.py` - 检查 backtest/profile API
  - `backend/app/api/model.py` - 检查 model-monitor API
  - `backend/app/api/task.py` - 检查 tasks API
  - `frontend/src/views/Profile.vue` - 添加调试日志
  - `frontend/src/views/Backtest.vue` - 添加错误处理
  - `frontend/src/views/ModelMonitor.vue` - 检查数据绑定

## ADDED Requirements

### Requirement: Fix NotFoundError Import Error
The system SHALL define `NotFoundError` class in `app.core.errors` module.

#### Scenario: Intraday page loads successfully
- **WHEN** user navigates to Intraday page and triggers data fetch
- **THEN** page should load without import error and display proper error message if no cache exists

### Requirement: Fix Profile Page Empty Data
The system SHALL return complete fund profile information including fund_name, establish_date, fund_size, manager, fee_rate.

#### Scenario: User enters valid fund code in Profile page
- **WHEN** user inputs fund code "018956" and clicks "查看画像"
- **THEN** system SHALL display complete profile information (fund name, type, size, manager, etc.)

### Requirement: Fix Backtest Data Display
The system SHALL return properly formatted backtest data with metrics field.

#### Scenario: User queries backtest for trained fund
- **WHEN** user selects fund code with existing backtest data and clicks query
- **THEN** system SHALL display backtest metrics (coverage, accuracy, MAE, RMSE, correlation)

### Requirement: Fix Train Task List Display
The system SHALL return complete task information including task_id and fund_code.

#### Scenario: User views training history
- **WHEN** user navigates to Train page
- **THEN** system SHALL display list of past tasks with task_id and fund_code columns populated

## MODIFIED Requirements

### Requirement: Error Handling Consistency
All error classes SHALL be defined in `app.core.errors` module and properly imported where needed.

### Requirement: Data Validation
API responses SHALL be validated before returning to frontend to ensure all required fields are present.
