"""语义记忆工具 — 存储和检索事实性知识。

全局共享（不按用户隔离），存储相对稳定的事实/配置。
检索时精确匹配优先，语义搜索兜底。

典型场景："航信项目用什么网段？"
"""

from __future__ import annotations

import logging
from typing import Annotated

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedStore
from langgraph.store.base import BaseStore

logger = logging.getLogger(__name__)


def _make_semantic_tools() -> list:
    """创建语义记忆工具（全局共享）。"""

    @tool
    def save_knowledge(
        category: str,
        key: str,
        value: str,
        confidence: float = 1.0,
        store: Annotated[BaseStore, InjectedStore()] = None,  # type: ignore[assignment]
    ) -> str:
        """保存一条事实知识到语义记忆。

        ⚠️ 仅在用户明确要求"记住"、"保存"、"记下来"时才调用此工具。
        当用户询问信息时（如"XX的信息你知道吗"），应该直接回答，不要调用此工具。

        用于存储相对稳定的事实（项目配置、技术栈、服务器信息等）。
        如果 key 已存在会更新。

        Args:
            category: 分类（如 "project_config"、"server_info"、"tech_stack"）
            key: 唯一标识（如 "tech_stack"、"航信网段"）
            value: 知识内容
            confidence: 置信度 0.0~1.0（默认 1.0）
        """
        if store is None:
            return "错误：Store 未启用"

        namespace = ("semantic", category)
        store.put(namespace, key, {
            "type": "semantic",
            "category": category,
            "key": key,
            "value": value,
            "confidence": confidence,
            "content": value,  # 用于向量检索的字段
        })
        logger.info("保存语义记忆: category=%s, key=%s", category, key)
        return f"已保存知识: [{category}] {key}"

    @tool
    def search_knowledge(
        query: str = "",
        category: str = "",
        key: str = "",
        limit: int = 5,
        store: Annotated[BaseStore, InjectedStore()] = None,  # type: ignore[assignment]
    ) -> str:
        """搜索事实知识。

        支持精确匹配（category + key）和语义搜索（query）。

        Args:
            query: 语义搜索关键词（自然语言描述）
            category: 限定分类（为空则搜索全部分类）
            key: 精确匹配 key（为空则不限制）
            limit: 返回数量上限
        """
        if store is None:
            return "错误：Store 未启用"

        # 精确匹配优先
        if category and key:
            ns = ("semantic", category)
            item = store.get(ns, key)
            if item:
                v = item.value
                return f"[{v.get('category', '')}] {v.get('key', '')}: {v.get('value', '')}"
            return f"未找到 [{category}].{key}"

        # 语义搜索
        if category:
            ns = ("semantic", category)
            results = store.search(ns, query=query, limit=limit)
        else:
            # 搜索全部分类下的顶层 namespace
            results = store.search(("semantic",), query=query, limit=limit)

        if not results:
            return "未找到相关知识"

        lines = []
        for item in results:
            v = item.value
            cat = v.get("category", "")
            key_str = v.get("key", "")
            val = v.get("value", "")[:300]
            lines.append(f"📌 [{cat}] {key_str}: {val}")
        return "\n\n".join(lines)

    return [save_knowledge, search_knowledge]
