"""
指数/ETF 型基金 Prompt 模板
重点分析：标的指数表现、跟踪误差
"""
from app.services.ai_prompt_templates.base_template import BaseTemplate, AnalysisContext


class IndexTemplate(BaseTemplate):
    """指数/ETF 型基金模板"""

    def build_type_specific_info(self, context: AnalysisContext) -> str:
        """构建指数/ETF 型基金的特定信息

        Args:
            context: 分析上下文

        Returns:
            指数型特定信息的 prompt 文本
        """
        extra = context.extra_info

        # 标的指数
        target_index_name = extra.get("target_index_name", "未知")
        target_index_code = extra.get("target_index_code", "")

        # 标的指数涨跌幅
        target_index_return = extra.get("target_index_return", 0)

        # 跟踪误差
        tracking_error_bp = extra.get("tracking_error_bp", "N/A")

        return f"""标的指数：{target_index_name}（{target_index_code}）
今日标的指数涨跌幅：{target_index_return:.4%}
跟踪误差（近20日）：{tracking_error_bp} BP

请重点分析：
1. 标的指数今日表现及主要成分股驱动
2. 注意：指数基金净值约等于标的指数涨跌幅，主要分析指数本身的变动原因"""
