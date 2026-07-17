"""程序记忆工具 — 存储和检索可复用的操作模式。

全局共享（不按用户隔离），存储从多次成功执行中抽象出的"剧本"。
检索时靠 trigger 场景匹配（向量相似度）。

典型场景："Docker 容器排障的标准步骤是什么？"
"""

from __future__ import annotations

import logging
from typing import Annotated

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedStore
from langgraph.store.base import BaseStore

logger = logging.getLogger(__name__)


def _make_procedural_tools() -> list:
    """创建程序记忆工具（全局共享）。"""

    namespace = ("procedural",)

    @tool
    def save_procedure(
        trigger: str,
        steps: list[str],
        description: str = "",
        store: Annotated[BaseStore, InjectedStore()] = None,  # type: ignore[assignment]
    ) -> str:
        """保存一个可复用的操作流程到程序记忆。

        用于存储从多次成功执行中总结的最佳实践。

        Args:
            trigger: 触发场景描述（如"用户要求处理退款"）
            steps: 操作步骤列表
            description: 简短描述
        """
        if store is None:
            return "错误：Store 未启用"

        # 用 trigger 生成 key
        key = trigger.replace(" ", "_")[:50]
        value = {
            "type": "procedural",
            "trigger": trigger,
            "steps": steps,
            "description": description,
            "success_rate": 1.0,
            "content": trigger,  # 用于向量检索的字段
        }
        store.put(namespace, key, value)
        logger.info("保存程序记忆: trigger=%s, steps=%d", trigger[:50], len(steps))
        return f"已保存操作流程: {trigger[:50]}（{len(steps)} 步）"

    @tool
    def match_procedure(
        scenario: str,
        limit: int = 3,
        store: Annotated[BaseStore, InjectedStore()] = None,  # type: ignore[assignment]
    ) -> str:
        """根据当前场景匹配操作流程。

        用向量相似度找到最匹配的操作流程。

        Args:
            scenario: 当前场景描述（如"帮我退款"、"Docker 容器起不来"）
            limit: 返回数量上限
        """
        if store is None:
            return "错误：Store 未启用"

        results = store.search(namespace, query=scenario, limit=limit)
        if not results:
            return "未找到匹配的操作流程"

        lines = []
        for item in results:
            v = item.value
            trigger = v.get("trigger", "")
            steps = v.get("steps", [])
            desc = v.get("description", "")
            steps_text = "\n".join(
                f"   {i}. {s}" for i, s in enumerate(steps, 1)
            )
            lines.append(f"🔧 场景: {trigger}")
            if desc:
                lines.append(f"   描述: {desc}")
            lines.append(f"   步骤:\n{steps_text}")
        return "\n\n---\n\n".join(lines)

    return [save_procedure, match_procedure]
