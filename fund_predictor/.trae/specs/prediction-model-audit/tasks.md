# Tasks

> 状态: 仅分析报告，不实施修改

- [x] 审查 prediction_service.py 全部函数 (predict_next, _direction_signal, _point_health, _direction_health, _current_regime, _intervals, _align_model_features, _model_feature_names, _clean_nan, _build_excess_signals, _load_model_monitoring)
- [x] 审查 routing_service.py 路由逻辑
- [x] 审查 model_registry_service.py 的存档/加载/append逻辑
- [x] 审查 feature_service.py 的 model_feature_columns 和 build_features 与预测的接口
- [x] 审查 model_selection_service.py 的点模型和方向模型训练逻辑
- [x] 汇总 16 个发现问题并按严重度分类
- [x] 确认无数据泄露、无回测逻辑错误的方面