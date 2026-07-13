"""互联网搜索工具 — 基于 Tavily API。

提供 Agent 可调用的网络搜索能力，用于查询最新的技术文档、
故障排查方案、软件版本信息等。

参考 deepagents 官方示例：
https://github.com/langchain-ai/deepagents
"""

from __future__ import annotations

import logging
import os
from typing import Literal

from tavily import TavilyClient

logger = logging.getLogger(__name__)

# 模块级别初始化 Tavily 客户端（懒加载，首次调用时检查 API Key）
_client: TavilyClient | None = None


def _get_client() -> TavilyClient:
    """获取 Tavily 客户端单例（懒加载）。

    Returns:
        TavilyClient 实例。

    Raises:
        RuntimeError: 未配置 TAVILY_API_KEY 环境变量时抛出。
    """
    global _client
    if _client is None:
        api_key = os.environ.get("TAVILY_API_KEY", "")
        if not api_key:
            raise RuntimeError(
                "未配置 TAVILY_API_KEY 环境变量，请在 .env 中设置。"
            )
        _client = TavilyClient(api_key=api_key)
        logger.info("Tavily 客户端已初始化")
    return _client


def internet_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
    include_raw_content: bool = False,
) -> str:
    """搜索互联网获取最新信息。

    适用于查询技术文档、故障排查方案、软件版本、新闻资讯等。
    返回搜索结果的摘要和来源链接。

    Args:
        query: 搜索关键词，用自然语言描述要查找的内容。
        max_results: 最大返回结果数，默认 5。
        topic: 搜索主题类型：
            - "general": 通用搜索（默认）
            - "news": 新闻资讯
            - "finance": 金融财经
        include_raw_content: 是否包含原始网页内容（可能很长），默认 False。

    Returns:
        搜索结果的格式化字符串，包含标题、摘要和 URL。
    """
    client = _get_client()
    logger.info("执行搜索: query=%s, topic=%s, max_results=%d", query, topic, max_results)

    result = client.search(
        query,
        max_results=max_results,
        include_raw_content=include_raw_content,
        topic=topic,
    )

    # 格式化搜索结果，便于 LLM 直接消费
    answer = result.get("answer", "")
    results = result.get("results", [])

    if not results:
        return "未找到相关搜索结果。"

    parts: list[str] = []
    if answer:
        parts.append(f"**摘要:** {answer}\n")

    parts.append(f"**搜索结果（共 {len(results)} 条）:**\n")
    for i, item in enumerate(results, 1):
        title = item.get("title", "无标题")
        url = item.get("url", "")
        content = item.get("content", "")
        # 截断过长的内容
        if len(content) > 800:
            content = content[:800] + "..."
        parts.append(f"{i}. **{title}**\n   URL: {url}\n   {content}\n")

        if include_raw_content and item.get("raw_content"):
            raw = item["raw_content"]
            if len(raw) > 4000:
                raw = raw[:4000] + "..."
            parts.append(f"   **原始内容:**\n   {raw}\n")

    output = "\n".join(parts)
    # 输出超过 8000 字符时截断
    if len(output) > 8000:
        output = output[:8000] + "\n... (结果已截断)"
        logger.warning("搜索结果已截断: 原始长度=%d", len(output))

    logger.info("搜索完成: 返回 %d 条结果", len(results))
    return output
