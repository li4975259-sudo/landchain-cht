from __future__ import annotations

import re

from app.config import Settings, get_settings

CHITCHAT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^(你好|您好|哈喽|嗨|hi|hello|hey)[!！?？。…~\s]*$", re.I),
    re.compile(r"^(早上好|下午好|晚上好|午安|晚安)[!！?？。…~\s]*$", re.I),
    re.compile(r"^(谢谢|多谢|感谢|thanks|thank you)[!！?？。…~\s]*$", re.I),
    re.compile(r"^(哈哈+|呵呵+|嘿嘿+|笑死|太搞笑了)[!！?？。…~\s]*$", re.I),
    re.compile(r"^(在吗|在不在|有人吗)[?？]?$", re.I),
    re.compile(r"^(你是谁|你叫什么|介绍一下你自己|你能做什么)[?？]?$", re.I),
    re.compile(r"^(讲个笑话|说个笑话|来个笑话)[?？]?$", re.I),
    re.compile(r"^(无聊|随便聊聊|聊聊天)[!！?？。…~\s]*$", re.I),
    re.compile(r"^(再见|拜拜|bye)[!！?？。…~\s]*$", re.I),
)

KNOWLEDGE_HINTS: tuple[str, ...] = (
    "订单",
    "金额",
    "价格",
    "文档",
    "查询",
    "搜索",
    "多少",
    "统计",
    "合计",
    "客户",
    "产品",
    "酒",
    "postgres",
    "landchain",
    "O0",
    "怀仁",
    "朔州",
    "知识库",
    "来源",
    "chunk",
)


def is_chitchat(message: str, settings: Settings | None = None) -> bool:
    """Return True when the message should bypass RAG and go direct to the LLM."""
    cfg = settings or get_settings()
    if not cfg.chitchat_direct_enabled:
        return False

    text = message.strip()
    if not text:
        return False

    lowered = text.lower()
    if any(hint.lower() in lowered for hint in KNOWLEDGE_HINTS):
        return False

    if len(text) <= cfg.chitchat_max_length:
        for pattern in CHITCHAT_PATTERNS:
            if pattern.match(text):
                return True

    for pattern in CHITCHAT_PATTERNS:
        if pattern.match(text):
            return True

    return False
