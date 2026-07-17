"""情景记忆工具 — 存储和检索用户的历史事件。

按用户隔离（namespace 含 user_id），存储有明确时间戳的交互事件。
检索时支持时间过滤 + 语义匹配。

典型场景："上次修 auth.py 的 bug 是怎么修的？"
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Annotated

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedStore
from langgraph.store.base import BaseStore

logger = logging.getLogger(__name__)


def _make_episodic_tools(user_id: str) -> list:
    """创建情景记忆工具（绑定 user_id）。"""

    namespace = ("episodic", user_id)

    @tool
    def save_event(
        event: str,
        context: str = "",
        outcome: str = "",
        files: str = "",
        tags: str = "",
        store: Annotated[BaseStore, InjectedStore()] = None,  # type: ignore[assignment]
    ) -> str:
        """保存一个历史事件到情景记忆。

        用于记录重要的操作事件，方便后续按时间或语义检索。

        Args:
            event: 事件描述（如"修复了 auth.py 的空指针异常"）
            context: 事件背景（如"用户报告登录页面 500 错误"）
            outcome: 结果（如"成功，pytest 全部通过"）
            files: 涉及的文件列表（JSON 数组或逗号分隔，如 '["auth.py"]' 或 "auth.py, config.py"）
            tags: 标签列表（JSON 数组或逗号分隔，如 '["bugfix","auth"]' 或 "bugfix, auth"）
        """
        if store is None:
            return "错误：Store 未启用"

        # 兼容 LLM 传 JSON 字符串或逗号分隔字符串
        import json as _json
        files_list: list[str] = []
        if files:
            try:
                parsed = _json.loads(files)
                if isinstance(parsed, list):
                    files_list = [str(f) for f in parsed]
            except (ValueError, TypeError):
                files_list = [f.strip() for f in files.split(",") if f.strip()]

        tags_list: list[str] = []
        if tags:
            try:
                parsed = _json.loads(tags)
                if isinstance(parsed, list):
                    tags_list = [str(t) for t in parsed]
            except (ValueError, TypeError):
                tags_list = [t.strip() for t in tags.split(",") if t.strip()]

        timestamp = datetime.now(timezone.utc).isoformat()
        key = f"event_{timestamp.replace(':', '-').replace('.', '_')}"

        value = {
            "type": "episodic",
            "timestamp": timestamp,
            "event": event,
            "context": context,
            "outcome": outcome,
            "files": files_list,
            "tags": tags_list,
        }
        store.put(namespace, key, value)
        logger.info("保存情景记忆: key=%s, event=%s", key, event[:80])
        return f"已保存事件: {event[:80]}"

    @tool
    def search_events(
        query: str = "",
        tag: str = "",
        limit: int = 5,
        store: Annotated[BaseStore, InjectedStore()] = None,  # type: ignore[assignment]
    ) -> str:
        """搜索历史事件。

        支持按标签精确过滤 + 语义匹配。

        Args:
            query: 搜索关键词（自然语言，用于语义匹配）
            tag: 按标签过滤（如 "auth"、"bugfix"）
            limit: 返回数量上限
        """
        if store is None:
            return "错误：Store 未启用"

        results = store.search(namespace, query=query or "", limit=limit)
        if not results:
            return "未找到相关事件"

        lines = []
        for item in results:
            v = item.value
            # 标签过滤
            if tag and tag not in v.get("tags", []):
                continue
            ts = v.get("timestamp", "")[:19]
            event = v.get("event", "")
            outcome = v.get("outcome", "")
            tags_str = ", ".join(v.get("tags", []))
            lines.append(f"📅 [{ts}] {event}")
            if outcome:
                lines.append(f"   结果: {outcome}")
            if tags_str:
                lines.append(f"   标签: {tags_str}")
        return "\n".join(lines) if lines else "未找到匹配标签的事件"

    return [save_event, search_events]
