import re
import logging
from app.core.errors import ValidationError

logger = logging.getLogger(__name__)


def normalize(raw_input: str) -> dict:
    steps = []
    text = raw_input.strip()
    text = text.replace("\u3000", " ")
    text = re.sub(r"\s+", "", text)
    steps.append("trim_whitespace")
    text = re.sub(r"\.(OF|SH|SZ)$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^(sh|sz)", "", text, flags=re.IGNORECASE)
    steps.append("remove_suffix_prefix")
    if re.match(r"^\d+$", text):
        while len(text) < 6:
            text = "0" + text
        steps.append("left_pad_zeros")
    if not re.match(r"^\d{6}$", text):
        return {
            "raw_input": raw_input,
            "normalized": text,
            "is_valid": False,
            "fund_name": "",
            "fund_type": None,
            "skip_prediction": None,
            "normalization_steps": steps,
        }
    steps.append("validate_format_6_digits")
    fund_name = ""
    fund_type = None
    skip_prediction = None
    try:
        import asyncio
        from app.services.data.danjuan_client import get_fund_info as dj_get_info
        loop = asyncio.get_event_loop()
        dj_data = loop.run_until_complete(dj_get_info(text))
        fund_name = dj_data.get("fund_name", "")
        if fund_name:
            steps.append("verify_danjuan")
    except Exception as e:
        logger.warning(f"danjuan验证失败 {text}: {e}, 尝试akshare")
        try:
            import akshare as ak
            df = ak.fund_individual_basic_info_xq(symbol=text)
            if df is not None and not df.empty:
                row = df.iloc[0]
                fund_name = str(row.get("基金简称", ""))
                fund_type_raw = str(row.get("基金类型", ""))
                if "货币" in fund_type_raw:
                    skip_prediction = True
                steps.append("verify_akshare")
        except Exception as e2:
            logger.warning(f"AKShare验证也失败 {text}: {e2}")
            steps.append("verify_all_failed")
    return {
        "raw_input": raw_input,
        "normalized": text,
        "is_valid": bool(fund_name),
        "fund_name": fund_name,
        "fund_type": fund_type,
        "skip_prediction": skip_prediction,
        "normalization_steps": steps,
    }