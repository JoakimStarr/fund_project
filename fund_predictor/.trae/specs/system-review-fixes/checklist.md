# Checklist

## Phase 1: 严重缺陷修复

- [x] 冷启动阈值与 MIN_TRAIN_ROWS(220) 对齐，120-220天基金不再报 InsufficientDataError
- [x] WF-CV 根据数据量动态调整参数，小数据集降级为 Hold-out 验证
- [x] 保形预测校准集明确使用 Test_select(13%)段，不复用 Valid 集
- [x] Benchmark "沪深300×80%+中债×20%" 正确分类为 hybrid_equity（非 hybrid_balanced）
- [x] 预测响应含 data_warning 字段标识数据滞后，_NAV_CACHE 有线程锁保护
- [x] 货币基金无论分类路径如何都统一走 skip_prediction=True

## Phase 2: 中等问题修复

- [x] 因子筛选 IC 使用 spearmanr (RankIC)，ic_threshold=0.02
- [x] 模型选择联合 MAE + 方向准确率，方向准确率<52%的候选模型被排除
- [x] VIF 筛选改为相关性聚类去重(|corr|>0.80归簇)，结果确定可复现
- [x] index_equity 类型绕过 ML 走规则引擎(index_ret × (1-fee))
- [x] 四段划分变量明确命名(X_train/X_valid/X_calib/X_final)，WF-CV 不触碰 X_final
- [x] 残差修正 recent_errors 来源明确定义(prediction_history表)，空表优雅降级

## Phase 3: 架构优化

- [x] _NAV_CACHE 所有读写路径受 threading.Lock 保护

## 全局验证

- [x] 现有 36 个测试不受影响且全部通过
- [x] 新增测试覆盖所有修改的关键路径
- [x] config.yaml 更新后的参数被代码正确读取
- [x] Docker compose 配置正确
