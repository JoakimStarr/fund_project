from app.services.ai.templates.base import BaseTemplate


class IndexTemplate(BaseTemplate):
    system_prompt = "你是一位专业的中国指数基金分析师。擅长分析标的指数走势和跟踪误差。只输出合法的JSON。"

    def _build_user_prompt(self, fund_data: dict, news_data: list, holdings_data: dict) -> str:
        fund_code = fund_data.get("fund_code", "")
        fund_name = fund_data.get("fund_name", "")
        news_text = "\n".join([f"- {getattr(n, 'title', n) if isinstance(n, dict) else n}" for n in news_data]) if news_data else "暂无相关新闻"
        return f"分析指数基金 {fund_name}({fund_code})。相关新闻：{news_text}。关注标的指数走势和跟踪误差。请输出JSON格式：summary, key_drivers, risk_factors, suggested_action(增持/持有/减持/观望), suggested_action_reason"