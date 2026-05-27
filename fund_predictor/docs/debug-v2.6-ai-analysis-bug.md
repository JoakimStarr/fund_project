# Debug Session: v2.6-ai-analysis-bug

**Session ID**: v2.6-ai-analysis-bug  
**Created**: 2026-05-26  
**Status**: FIXED ✅  
**Fixed At**: 2026-05-26 15:30 UTC+8

---

## 📋 Bug 描述

在实施技术文档 v2.6.0 的 AI 分析与新闻聚合模块后，发现以下问题：
1. 数据库缺少 ai_analysis_cache 表的创建逻辑
2. 前端构建失败（terser 依赖缺失）

---

## 🔬 Hypotheses (验证结果)

| # | Hypothesis | Status | Evidence |
|---|------------|--------|----------|
| H1 | 后端 Python 导入错误 | ❌ 排除 | 所有 .py 文件语法检查通过 |
| H2 | API 路由未注册 | ❌ 排除 | main.py 正确导入和注册 |
| H3 | 配置加载失败 | ❌ 排除 | config.yaml 正常解析 |
| **H4** | **数据库表缺失** | **✅ 确认** | **database.py 缺少 CREATE TABLE 语句** |
| H5 | 前端编译错误 | ⚠️ 部分确认 | terser 依赖导致构建失败 |

---

## 🔧 Fixes Applied

### Fix #1: database.py - 添加 ai_analysis_cache 表
**File**: `/backend/app/db/database.py`  
**Change**: 在 `_init_schema()` 函数中添加了完整的 CREATE TABLE 和索引创建语句
```sql
CREATE TABLE IF NOT EXISTS ai_analysis_cache (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    fund_code       TEXT NOT NULL,
    trade_date      TEXT NOT NULL,
    source          TEXT NOT NULL,
    analysis_json   TEXT NOT NULL,
    provider_used   TEXT,
    model_used      TEXT,
    news_count      INTEGER DEFAULT 0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(fund_code, trade_date, source)
);
```
**Indexes Created**:
- `idx_ai_cache_fund_date` ON (fund_code, trade_date)
- `idx_ai_cache_created` ON (created_at)

### Fix #2: vite.config.js - 替换 terser 为 esbuild
**File**: `/frontend/vite.config.js`  
**Change**: `minify: 'terser'` → `minify: 'esbuild'`  
**Reason**: esbuild 是 Vite 默认推荐，速度更快且无需额外依赖安装

---

## ✅ Verification Results

### Pre-Fix (Before)
```
❌ 前端构建失败: Cannot find module 'terser'
❌ 数据库测试: ai_analysis_cache 表不存在
```

### Post-Fix (After)
```
✅ 前端构建成功: built in 7.11s (exit code 0)
✅ 数据库测试: 
   - ai_analysis_cache 表创建成功
   - 3个索引全部创建成功
   - 9个字段完整
```

---

## 📊 Impact Assessment

**Files Modified**: 2 files  
**Lines Changed**: +20 lines / -1 line  
**Breaking Changes**: None  
**Backward Compatibility**: ✅ 完全兼容  

---

## 🎯 Root Cause Summary

1. **数据库表遗漏**: 在实现 AI 分析服务时，忘记在 database.py 的 `_init_schema()` 函数中添加 `ai_analysis_cache` 表的 DDL 语句。这是一个典型的"新功能遗漏"型 bug。

2. **Vite 配置过时**: 项目使用了 Vite v3.x，但配置中仍指定使用 `minify: 'terser'`（Vite v2.x 的默认值）。Vite v3+ 推荐 esbuild 作为默认压缩工具。

---

## 🚀 Lessons Learned

1. **DDL 与 ORM 模型同步**: 添加新的数据模型时，必须同时更新数据库初始化脚本
2. **Vite 版本适配**: 升级 Vite 版本时需检查 build 配置是否需要更新
3. **自动化验证**: 应该添加 CI/CD 步骤自动运行 `npm run build` 和数据库初始化测试

---

## 🧹 Cleanup Status

✅ All instrumentation removed  
✅ Debug server stopped  
✅ This file ready for archival  
