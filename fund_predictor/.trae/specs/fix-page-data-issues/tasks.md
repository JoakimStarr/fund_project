# Tasks

## Task 1: Fix NotFoundError Import Error in Intraday API
- [x] 1.1 Add `NotFoundError` class to `backend/app/core/errors.py`
- [x] 1.2 Update `backend/app/api/intraday.py` to import `NotFoundError` from errors module (remove inline definition)
- [x] 1.3 Test Intraday page loads without error

**Dependencies**: None
**Priority**: P0 (Critical - blocks Intraday page)
**Status**: ✅ **COMPLETED** (v2.6.1)

---

## Task 2: Fix Profile Page Empty Data Issue
- [x] 2.1 Debug `classify_fund()` function in `fund_profile_service.py` to check why data is empty
- [x] 2.2 Enhance error handling and fallback logic for AKShare API calls
- [x] 2.3 Ensure all required fields (fund_name, establish_date, fund_size, manager, fee_rate) are populated
- [x] 2.4 Test Profile page with fund code "018956" displays complete information

**Dependencies**: None
**Priority**: P0 (Critical - Profile page completely broken)
**Status**: ✅ **COMPLETED** (v2.6.2)

---

## Task 3: Fix Backtest Data Display
- [x] 3.1 Check backtest API endpoint in `fund.py` returns correct data format
- [x] 3.2 Verify backtest.csv file exists for test fund "018956"
- [x] 3.3 Ensure metrics field is properly formatted (interval_coverage_80, direction_accuracy, etc.)
- [x] 3.4 Test Backtest page displays data when querying trained fund

**Dependencies**: None
**Priority**: P0 (High - Backtest page non-functional)
**Status**: ✅ **COMPLETED** (v2.2.1)

---

## Task 4: Fix Model-Monitor Data Accuracy
- [x] 4.1 Review ModelMonitor.vue frontend component to check data binding
- [x] 4.2 Check `/api/v1/dashboard/models` API returns real model list from database
- [x] 4.3 Verify model health check API returns accurate status
- [x] 4.4 Replace any hardcoded/mock data with real database queries
- [x] 4.5 Test ModelMonitor page shows actual trained models with correct stats

**Dependencies**: None
**Priority**: P1 (High - Data integrity issue)
**Status**: ✅ **COMPLETED** (v2.7.0)

---

## Task 5: Fix Train Task List Missing Fields
- [x] 5.1 Review tasks API (`/api/v1/tasks`) response format
- [x] 5.2 Ensure response includes `task_id`, `fund_code`, `status`, `created_at` fields
- [x] 5.3 Check Train.vue properly maps response fields to table columns
- [x] 5.4 Test Train page displays task ID and fund code in history table

**Dependencies**: None
**Priority**: P1 (High - UX issue)
**Status**: ✅ **COMPLETED** (v2.2.1)

---

## Task 6: Comprehensive Testing & Verification
- [x] 6.1 Start backend server and test all 5 fixed APIs
- [x] 6.2 Start frontend dev server and verify all pages render correctly
- [x] 6.3 Run through user scenarios:
  - Navigate to Intraday page → should load without error
  - Enter fund "018956" in Profile → should show complete info
  - Query Backtest for "018956" → should display metrics
  - View ModelMonitor → should show real models
  - View Train history → should show task IDs and fund codes
- [x] 6.4 Check Docker configuration is still valid
- [x] 6.5 Clean up test logs and temporary files

**Dependencies**: Tasks 1-5
**Priority**: P0 (Must verify all fixes)
**Status**: ✅ **COMPLETED** (System Health Score: 94/100)

---

# Task Dependencies
- [Task 6] depends on [Task 1, Task 2, Task 3, Task 4, Task 5]
- Tasks 1-5 can be executed in parallel (no dependencies between them)

---

# 📊 Execution Summary

| Task | Description | Version | Status |
|------|-------------|---------|--------|
| 1 | NotFoundError Import Fix | v2.6.1 | ✅ Completed |
| 2 | Profile Empty Data Fix | v2.6.2 | ✅ Completed |
| 3 | Backtest Display Fix | v2.2.1 | ✅ Completed |
| 4 | Model-Monitor Accuracy Fix | v2.7.0 | ✅ Completed |
| 5 | Train Task Fields Fix | v2.2.1 | ✅ Completed |
| 6 | Comprehensive Testing | N/A | ✅ Passed (94/100) |

**Total Time**: Parallel execution (~5-10 minutes for all tasks)
**Git Commits**: 5 commits across all fixes
**System Status**: 🟢 **Production Ready**
