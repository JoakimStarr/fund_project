"""
基础 Prompt 模板：所有模板共享的输出格式约束和角色设定
适用于货币型、FOF 等未单独设计模板的基金类型
"""
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class AnalysisContext:
    """AI 分析上下文数据（所有模板共用）"""
    fund_code: str
    fund_name: str
    fund_type: str
    fund_type_display: str
    estimated_return: float
    lower_bound: float
    upper_bound: float
    source: str  # "intraday" 或 "predict"
    method_display: str = ""
    holdings_freshness_note: str = ""
    news_items: list[dict] = field(default_factory=list)
    # 可选扩展字段
    extra_info: dict[str, Any] = field(default_factory=dict)


class BaseTemplate(ABC):
    """Prompt 模板基类"""

    ROLE_PROMPT = """你是一位专业的中国基金分析师。请根据以下信息，生成一份简短的当日分析报告。
注意：持仓数据来自季报，存在滞后性。当持仓数据较旧时，请在分析中明确说明不确定性，避免过于确定的表述。"""

    OUTPUT_FORMAT = """请严格按照以下JSON格式输出，不要输出任何JSON以外的内容（不要有```json标记）：
{
  "summary": "总体分析（100字以内，客观表述，不做投资承诺）",
  "key_drivers": [
    {"factor": "驱动因素名称", "direction": "正向或负向", "desc": "一句话说明"}
  ],
  "risk_factors": ["风险点1", "风险点2"],
  "suggested_action": "以下四个之一：增持/持有/减持/观望",
  "suggested_action_reason": "建议理由（30字以内）"
}
注意：suggested_action 只能是"增持""持有""减持""观望"之一，不得输出其他词语。"""

    def build_news_section(self, news_items: list[dict]) -> str:
        """构建新闻部分文本

        Args:
            news_items: 新闻列表

        Returns:
            新闻部分的 prompt 文本
        """
        if not news_items:
            return "暂无直接相关新闻"

        lines = []
        for i, item in enumerate(news_items[:3], 1):
            title = item.get("title", "")
            source = item.get("source", "")
            score = item.get("relevance_score", 0)
            lines.append(f"{i}. [{source}] {title} (相关度:{score:.2f})")

        return "\n".join(lines)

    @abstractmethod
    def build_type_specific_info(self, context: AnalysisContext) -> str:
        """构建类型特定信息（子类实现）

        Args:
            context: 分析上下文

        Returns:
            类型特定的 prompt 文本
        """
        pass

    def build_prompt(self, context: AnalysisContext) -> str:
        """组装完整的 Prompt

        Args:
            context: 分析上下文数据

        Returns:
            完整的 prompt 字符串
        """
        type_info = self.build_type_specific_info(context)
        news_content = self.build_news_section(context.news_items)

        method_map = {
            "intraday": "盘中实时估算",
            "predict": "T+1 预测模型",
        }
        method_display = context.method_display or method_map.get(context.source, "估算")

        prompt = f"""{self.ROLE_PROMPT}

[基金信息]
代码：{context.fund_code}
名称：{context.fund_name}
类型：{context.fund_type_display}
{type_info}

[估算/预测数据]
今日估算涨跌幅：{context.estimated_return:.4%}
置信区间：[{context.lower_bound:.4%}, {context.upper_bound:.4%}]
估算方法：{method_display}
{context.holdings_freshness_note}

[今日相关新闻]（共{len(context.news_items)}条）
{news_content}

{self.OUTPUT_FORMAT}"""

        return prompt

    def parse_response(self, response_text: str, allowed_actions: list[str]) -> dict:
        """解析 AI 响应，提取 JSON 结构化结果

        多重容错机制：
        1. 直接 json.loads
        2. 正则提取 {...}
        3. 降级返回截断文本

        Args:
            response_text: AI 原始响应
            allowed_actions: 允许的操作白名单

        Returns:
            结构化的分析结果字典
        """
        result = None

        # Step 1: 尝试直接解析
        try:
            result = json.loads(response_text.strip())
        except json.JSONDecodeError:
            pass

        # Step 2: 正则提取
        if result is None:
            import re
            match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if match:
                try:
                    result = json.loads(match.group())
                except json.JSONDecodeError:
                    pass

        # Step 3: 降级处理
        if result is None:
            return {
                "summary": response_text[:200] if len(response_text) > 200 else response_text,
                "key_drivers": [],
                "risk_factors": [],
                "suggested_action": "观望",
                "suggested_action_reason": "AI解析异常，建议人工判断",
            }

        # 字段校验和修正
        return self._validate_and_clean(result, allowed_actions)

    def _validate_and_clean(self, result: dict, allowed_actions: list[str]) -> dict:
        """校验并清理 AI 输出字段

        Args:
            result: 解析后的结果字典
            allowed_actions: 允许的操作列表

        Returns:
            清理后的结果字典
        """
        # suggested_action 白名单检查
        action = result.get("suggested_action", "观望")
        if action not in allowed_actions:
            result["suggested_action"] = "观望"

        # summary 截断
        summary = result.get("summary", "")
        if len(summary) > 300:
            result["summary"] = summary[:300]

        # key_drivers 截断
        drivers = result.get("key_drivers", [])
        if len(drivers) > 5:
            result["key_drivers"] = drivers[:5]

        # risk_factors 截断
        risks = result.get("risk_factors", [])
        if len(risks) > 4:
            result["risk_factors"] = risks[:4]

        # 确保必要字段存在
        result.setdefault("summary", "")
        result.setdefault("key_drivers", [])
        result.setdefault("risk_factors", [])
        result.setdefault("suggested_action", "观望")
        result.setdefault("suggested_action_reason", "")

        return result
