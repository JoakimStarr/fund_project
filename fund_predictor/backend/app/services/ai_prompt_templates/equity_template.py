"""
偏股/主动股票型基金 Prompt 模板
重点分析：重仓股表现、大盘β效应、行业催化剂
"""
from app.services.ai_prompt_templates.base_template import BaseTemplate, AnalysisContext


class EquityTemplate(BaseTemplate):
    """偏股/主动股票型基金模板"""

    def build_type_specific_info(self, context: AnalysisContext) -> str:
        """构建股票型基金的特定信息

        Args:
            context: 分析上下文

        Returns:
            股票型特定信息的 prompt 文本
        """
        extra = context.extra_info

        # 重仓股列表
        top10_holdings = extra.get("top10_holdings_list", "暂无持仓数据")

        # 重仓股实时表现
        holdings_realtime = extra.get("holdings_realtime_summary", "暂无实时行情数据")

        # 行业暴露
        sector_exposure = extra.get("sector_exposure", "未知")

        # 风格标签
        style_label = extra.get("style_label", "未知")

        return f"""前十大重仓股（按权重）：
{top10_holdings}

重仓股今日估算涨跌（基于实时行情）：
{holdings_realtime}

主要行业暴露：{sector_exposure}
风格偏向：{style_label}（大盘/小盘/成长/价值）

请重点分析：
1. 重仓股今日表现对净值的贡献
2. 大盘指数走势的影响（β效应）
3. 行业或主题的近期催化剂"""
