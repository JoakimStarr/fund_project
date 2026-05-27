"""
平衡/灵活混合型基金 Prompt 模板
综合分析股票和债券双方向影响
"""
from app.services.ai_prompt_templates.base_template import BaseTemplate, AnalysisContext


class MixedTemplate(BaseTemplate):
    """平衡/灵活混合型基金模板"""

    def build_type_specific_info(self, context: AnalysisContext) -> str:
        """构建混合型基金的特定信息

        Args:
            context: 分析上下文

        Returns:
            混合型特定信息的 prompt 文本
        """
        extra = context.extra_info

        # 估算仓位
        equity_position = extra.get("estimated_equity_position", "未知")
        bond_position = extra.get("estimated_bond_position", "未知")

        # 市场数据
        hs300_return = extra.get("hs300_return", "N/A")
        cn10y_change = extra.get("cn10y_change", "N/A")

        # 重仓股信息（如果有）
        top10_holdings = extra.get("top10_holdings_list", "")

        additional_info = ""
        if top10_holdings:
            additional_info = f"\n\n前十大重仓股（按权重）：\n{top10_holdings}"

        return f"""估算股票仓位：{equity_position}
估算债券仓位：{bond_position}

当日主要市场数据：
- 沪深300：{hs300_return}
- 10年国债收益率变动：{cn10y_change} BP
{additional_info}

请综合分析股票和债券双方向的影响，根据估算仓位判断哪个方向的贡献更大。"""
