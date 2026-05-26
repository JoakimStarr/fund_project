"""
AI Prompt 模板体系：按基金类型分类的 Prompt 构建器
"""
from app.services.ai_prompt_templates.base_template import BaseTemplate
from app.services.ai_prompt_templates.equity_template import EquityTemplate
from app.services.ai_prompt_templates.bond_template import BondTemplate
from app.services.ai_prompt_templates.index_template import IndexTemplate
from app.services.ai_prompt_templates.mixed_template import MixedTemplate

TEMPLATE_REGISTRY = {
    "equity_active": EquityTemplate,
    "equity_index": IndexTemplate,
    "bond": BondTemplate,
    "mixed_equity": MixedTemplate,
    "hybrid_flexible": MixedTemplate,
    "money_market": BaseTemplate,
    "fof": BaseTemplate,
}


def get_template(fund_type: str) -> BaseTemplate:
    """根据基金类型获取对应的 Prompt 模板

    Args:
        fund_type: 基金类型标识

    Returns:
        对应的模板实例
    """
    template_cls = TEMPLATE_REGISTRY.get(fund_type, BaseTemplate)
    return template_cls()
