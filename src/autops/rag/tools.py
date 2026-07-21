"""RAGFlow 知识库检索工具 — Agent 可调用的 search_rag_knowledge。"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def search_rag_knowledge(
    query: str,
    top_k: int = 5,
) -> str:
    """从运维知识库（RAGFlow）中检索相关内容。

    适用于查询运维文档、故障排查方案、操作手册、配置规范、架构说明等。
    返回匹配的知识片段及来源引用。

    Args:
        query: 检索关键词（自然语言描述要查找的内容）。
        top_k: 返回结果数量上限，默认 5。

    Returns:
        检索结果的格式化字符串，包含内容片段和来源引用。
    """
    from autops.rag.client import get_ragflow_client

    client = get_ragflow_client()
    if client is None:
        return "知识库检索未启用（RAGFlow 未配置或不可用）。"

    try:
        chunks = client.retrieve(question=query, top_k=top_k)
    except Exception as e:
        logger.error("RAGFlow 检索异常: %s", e)
        return f"知识库检索失败: {e}"

    if not chunks:
        return "未找到相关知识。"

    parts: list[str] = []
    parts.append(f"**知识库检索结果（共 {len(chunks)} 条）:**\n")

    for i, chunk in enumerate(chunks, 1):
        content = chunk.get("content", chunk.get("content_with_weight", ""))
        # 去除权重标记（RAGFlow 格式: "内容 #123#"）
        if " #" in content and content.rstrip().endswith("#"):
            content = content.rsplit(" #", 1)[0]

        doc_name = chunk.get("document_keyword", "") or chunk.get("document_name", "")
        similarity = chunk.get("similarity", 0)
        dataset_name = chunk.get("dataset_keyword", "") or chunk.get("dataset_name", "")

        # 截断过长内容
        if len(content) > 1000:
            content = content[:1000] + "..."

        parts.append(f"{i}. {content}")
        source_parts = []
        if doc_name:
            source_parts.append(f"文档: {doc_name}")
        if dataset_name:
            source_parts.append(f"知识库: {dataset_name}")
        if similarity:
            source_parts.append(f"相似度: {similarity:.2f}")
        if source_parts:
            parts.append(f"   来源: {' | '.join(source_parts)}")
        parts.append("")

    output = "\n".join(parts)
    if len(output) > 8000:
        output = output[:8000] + "\n\n... (结果已截断)"

    logger.info("知识库检索完成: query=%r, 返回 %d 条", query[:80], len(chunks))
    return output
