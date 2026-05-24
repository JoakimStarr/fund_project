# Checklist

- [x] prediction_service.py 的 predict_next 全部代码路径已审查
- [x] _direction_signal 阈值逻辑已分析
- [x] _current_regime 的 vol_col fallback 和阈值判断已逐行验证
- [x] _intervals 的 quantile fallback 逻辑已验证
- [x] _align_model_features 的缺失特征填充行为已确认
- [x] _model_feature_names 的多层回退机制已验证
- [x] _clean_nan 递归遍历覆盖所有嵌套结构
- [x] _build_excess_signals 的 NaN 安全处理已验证
- [x] routing_service.py 的 route_predict 实际路由效果已确认
- [x] model_registry 的 append_prediction 竞态条件已识别
- [x] model_registry 的 save_model_archive 存档完整性已验证
- [x] feature_service 的 model_feature_columns 泄露防护已确认
- [x] build_features 的返回值结构与调用方的一致性已验证
- [x] model_selection 的 _point_model 全量重训逻辑已确认
- [x] model_selection 的 _direction_model train/test_split 差异已识别
- [x] model_selection 的 _regime_intervals 分位数方法已分析
- [x] 汇总表覆盖所有发现问题，含文件+行号