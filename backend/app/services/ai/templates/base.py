class BaseTemplate:
    system_prompt = "你是一位专业的中国基金分析师。只输出合法的JSON。"

    def build_prompt(self, fund_data: dict, news_data: list, holdings_data: dict) -> list:
        messages = [{"role": "system", "content": self.system_prompt}]
        prompt = self._build_user_prompt(fund_data, news_data, holdings_data)
        messages.append({"role": "user", "content": prompt})
        return messages

    def _build_user_prompt(self, fund_data: dict, news_data: list, holdings_data: dict) -> str:
        fund_code = fund_data.get("fund_code", "")
        fund_name = fund_data.get("fund_name", "")
        fund_type = fund_data.get("fund_type", "")
        news_text = "\n".join([f"- {getattr(n, 'title', n) if isinstance(n, dict) else n}" for n in news_data]) if news_data else "暂无相关新闻"
        holdings_summary = holdings_data.get("summary", "暂无持仓数据")
        return f"分析基金 {fund_name}({fund_code})，类型：{fund_type}。持仓：{holdings_summary}。相关新闻：{news_text}。请输出JSON格式：summary, key_drivers, risk_factors, suggested_action(增持/持有/减持/观望), suggested_action_reason"