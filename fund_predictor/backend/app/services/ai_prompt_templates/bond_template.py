"""
债券型基金 Prompt 模板
重点分析：利率变动、信用利差、资金面
"""
from app.services.ai_prompt_templates.base_template import BaseTemplate, AnalysisContext


class BondTemplate(BaseTemplate):
    """债券型基金模板"""

    def build_type_specific_info(self, context: AnalysisContext) -> str:
        """构建债券型基金的特定信息

        Args:
            context: 分析上下文

        Returns:
            债券型特定信息的 prompt 文本
        """
        extra = context.extra_info

        # 组合久期
        duration = extra.get("duration", "未知")

        # 债券类型
        bond_subtype = extra.get("bond_subtype_display", "未知")

        # 利率数据
        cn10y_change = extra.get("cn10y_change", "N/A")
        term_spread = extra.get("term_spread", "N/A")
        term_spread_change = extra.get("term_spread_change", "N/A")
        dr007 = extra.get("dr007", "N/A")
        credit_spread_aaa = extra.get("credit_spread_aaa", "N/A")

        return f"""估算组合久期：{duration}年
债券类型：{bond_subtype}

今日关键利率数据（来自AKShare）：
- 10年期国债收益率变动：{cn10y_change} BP
- 期限利差（10Y-2Y）：{term_spread} BP，较昨日变动 {term_spread_change} BP
- DR007：{dr007}%
- 信用利差（AAA）：{credit_spread_aaa} BP

请重点分析：
1. 利率变动对债券净值的直接影响（公式：ΔNAV≈-久期×Δy）
2. 信用利差变化的影响
3. 资金面松紧程度（DR007水平）
（注意：债券基金不受股市涨跌直接影响，请勿将股市新闻作为主要驱动因素）"""
