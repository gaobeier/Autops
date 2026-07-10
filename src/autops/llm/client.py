"""LLM 客户端封装 — 基于 LangChain ChatOpenAI。"""

from __future__ import annotations

from langchain_openai import ChatOpenAI

from autops.config.settings import config


def create_llm() -> ChatOpenAI:
    """根据 config.yaml 中的 LLM 配置创建 ChatOpenAI 实例。

    支持 OpenAI 兼容的 API（如阿里云百炼 DashScope）。

    Returns:
        配置好的 ChatOpenAI 实例。
    """
    llm_cfg = config.llm
    return ChatOpenAI(
        model=llm_cfg.model,
        api_key=llm_cfg.api_key,
        base_url=llm_cfg.base_url,
        temperature=llm_cfg.temperature,
        # max_tokens=llm_cfg.max_tokens,
    )
