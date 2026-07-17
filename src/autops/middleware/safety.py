"""命令安全中间件 — 拦截高危命令，直接拒绝执行。

高危命令（rm -rf /、dd 写裸盘、fork bomb 等）在工具执行前被拦截，
直接返回错误 ToolMessage，不经过审批流程。

危险命令由 HumanInTheLoopMiddleware 的 when 谓词处理（触发审批）。
"""

from __future__ import annotations

import logging
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import AgentState, ContextT, ResponseT
from langchain_core.messages import ToolMessage

from autops.tools.dangerous_commands import assess_command

logger = logging.getLogger(__name__)


class CommandSafetyMiddleware(AgentMiddleware[AgentState, ContextT, ResponseT]):
    """拦截高危 execute 命令，直接拒绝执行。

    高危命令不执行也不审批，直接返回错误信息给 Agent。
    危险命令的审批由 HumanInTheLoopMiddleware 处理。
    """

    def _check_and_intercept(self, request: Any) -> ToolMessage | None:
        """检查是否高危命令，高危则返回错误 ToolMessage，否则返回 None。

        同步逻辑，供 wrap_tool_call 和 awrap_tool_call 共用。
        """
        tool_call = getattr(request, "tool_call", None) or {}
        if not isinstance(tool_call, dict):
            return None

        name = tool_call.get("name", "")
        if name != "execute":
            return None

        args = tool_call.get("args", {})
        if not isinstance(args, dict):
            return None
        command = args.get("command", "")
        if not command:
            return None

        # 加载安全配置
        from autops.config.settings import config
        safety = config.agent.safety

        level, reason = assess_command(
            command,
            dangerous_commands=safety.dangerous_commands,
            dangerous_paths=safety.dangerous_paths,
        )

        if level == "critical":
            tool_call_id = tool_call.get("id", "")
            logger.warning("拒绝高危命令: %r, 原因: %s", command, reason)
            return ToolMessage(
                content=f"拒绝执行: {reason}。此操作被安全策略禁止。",
                name="execute",
                tool_call_id=tool_call_id,
                status="error",
            )

        logger.debug("命令安全检查通过: level=%s, command=%r", level, command)
        return None

    def wrap_tool_call(
        self,
        request: Any,
        handler: Any,
    ) -> Any:
        """同步版本：拦截高危命令。"""
        result = self._check_and_intercept(request)
        if result is not None:
            return result
        return handler(request)

    async def awrap_tool_call(
        self,
        request: Any,
        handler: Any,
    ) -> Any:
        """异步版本：拦截高危命令（LangGraph dev 异步执行时调用）。"""
        result = self._check_and_intercept(request)
        if result is not None:
            return result
        # 异步上下文中 handler 是 async callable，需要 await
        return await handler(request)
