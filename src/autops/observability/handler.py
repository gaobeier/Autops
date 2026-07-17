"""Agent 可观测性回调处理器 — 通用、与 channel 无关。

职责：
- 每次 LLM 调用递增 Turn 号、记录耗时
- 工具调用时通过 EventSink 实时通知
- 调用结束后通过 summary() 返回精简统计
- 跟踪 token 用量：单次 input/output + 当前上下文窗口占用及分项占比

使用方式：
    from autops.observability import AgentObservabilityHandler, NullEventSink

    handler = AgentObservabilityHandler(sink=NullEventSink())
    result = agent.invoke(..., config={"callbacks": [handler]})
    print(handler.summary())
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler

from autops.config.settings import config
from autops.observability.sink import EventSink, NullEventSink, safe_call

logger = logging.getLogger(__name__)


def _truncate(text: Any, max_len: int = 500) -> str:
    """截断过长的文本用于日志展示。"""
    s = str(text)
    return s if len(s) <= max_len else s[:max_len] + "..."


class AgentObservabilityHandler(BaseCallbackHandler):
    """Agent 可观测性回调处理器。

    Args:
        sink: EventSink 实现，用于接收实时事件通知。
               不传时使用 NullEventSink（仅日志，不外发通知）。
    """

    # 常见模型的上下文窗口大小（Qwen 等专有模型需手动配置）
    DEFAULT_CONTEXT_WINDOW = {
        "qwen3.7-plus": 128_000,   # 阿里云通义千问
        "qwen-plus": 128_000,
        "qwen-turbo": 128_000,
        "gpt-4o": 128_000,
        "gpt-4o-mini": 128_000,
        "gpt-4-turbo": 128_000,
        "claude-sonnet-4": 200_000,
        "claude-opus-4": 200_000,
    }
    FALLBACK_CONTEXT_WINDOW = 128_000

    def __init__(self, sink: EventSink | None = None) -> None:
        self._timings: dict[UUID, float] = {}
        self._tool_names: dict[UUID, str] = {}
        self._sink: EventSink = sink or NullEventSink()
        self._start_time = time.monotonic()
        self._model_name = config.llm.model
        self._turn = 0
        self._total_prompt_tokens = 0
        self._total_completion_tokens = 0
        self._tool_count = 0

        # ── Token 用量追踪（最新一次 LLM 调用的完整 prompt 分项统计）──
        self._last_messages: list = []              # 最近一次调用的 messages
        self._last_system_text: str = ""             # 最近一次 system_message 文本
        self._last_tools_text: str = ""              # 最近一次 tools schema 文本
        self._last_input_tokens: int = 0             # 最近一次 input_tokens（API 返回）
        self._last_output_tokens: int = 0            # 最近一次 output_tokens
        self._context_window: int = self._resolve_context_window()
        # tiktoken 编码器（懒加载）
        self._encoder = None

    def _resolve_context_window(self) -> int:
        """解析当前模型的上下文窗口大小。

        优先级：
        1. 模型 profile（langchain model.profile.get("max_input_tokens")）
        2. 已知模型表（DEFAULT_CONTEXT_WINDOW）
        3. 默认值（FALLBACK_CONTEXT_WINDOW = 128K）
        """
        try:
            from autops.llm.client import create_llm
            model = create_llm()
            profile_max = (
                model.profile.get("max_input_tokens")
                if hasattr(model, "profile") and model.profile
                else None
            )
            if profile_max:
                return int(profile_max)
        except Exception:  # noqa: BLE001
            pass

        for key, window in self.DEFAULT_CONTEXT_WINDOW.items():
            if key in self._model_name:
                return window
        return self.FALLBACK_CONTEXT_WINDOW

    def _get_encoder(self):
        """懒加载 tiktoken 编码器（与 OpenAI 模型族兼容）。"""
        if self._encoder is None:
            import tiktoken
            try:
                self._encoder = tiktoken.encoding_for_model("gpt-4o")
            except Exception:
                self._encoder = tiktoken.get_encoding("cl100k_base")
        return self._encoder

    def _count_tokens(self, text: str) -> int:
        """用 tiktoken 计算 token 数。"""
        if not text:
            return 0
        try:
            return len(self._get_encoder().encode(text))
        except Exception:  # noqa: BLE001
            # 兜底：粗略估算（4 字符 ≈ 1 token，对中文稍偏多）
            return len(text) // 4

    def _extract_message_text(self, msg) -> str:
        """从消息对象提取纯文本内容（支持多模态/工具结果嵌套）。"""
        content = getattr(msg, "content", None)
        # 字符串内容
        if isinstance(content, str):
            return content
        # list 类型（Anthropic 风格的 content blocks）
        if isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if isinstance(block, str):
                    parts.append(block)
                elif isinstance(block, dict):
                    btype = block.get("type")
                    if btype == "text":
                        parts.append(block.get("text", ""))
                    elif btype == "tool_use":
                        # 工具调用入参
                        parts.append(json.dumps(block.get("input", {}), ensure_ascii=False))
                    elif btype == "tool_result":
                        # 工具结果，content 字段可能是 str / list / dict
                        tc = block.get("content", "")
                        if isinstance(tc, str):
                            parts.append(tc)
                        elif isinstance(tc, list):
                            # 嵌套的 content blocks
                            for sub in tc:
                                if isinstance(sub, str):
                                    parts.append(sub)
                                elif isinstance(sub, dict) and sub.get("type") == "text":
                                    parts.append(sub.get("text", ""))
                                else:
                                    parts.append(json.dumps(sub, ensure_ascii=False))
                        else:
                            parts.append(json.dumps(tc, ensure_ascii=False))
                    elif btype == "thinking":
                        # Claude 思考块（跳过，不计入消息统计）
                        pass
                    else:
                        parts.append(json.dumps(block, ensure_ascii=False))
            return "\n".join(parts)
        # 其他类型（dict 等）
        if content is None:
            # AIMessage 可能没有 content 但有 tool_calls
            tool_calls = getattr(msg, "tool_calls", None) or []
            if tool_calls:
                return json.dumps(tool_calls, ensure_ascii=False)
            return ""
        return str(content)

    # ── LLM 相关 ────────────────────────────────────────────────

    def on_chat_model_start(
        self, serialized: dict, messages: list, *, run_id: UUID, **kwargs: Any
    ) -> None:
        kwargs_data = serialized.get("kwargs", {})
        model = kwargs_data.get("model_name") or kwargs_data.get("model") or self._model_name
        self._model_name = model
        self._timings[run_id] = time.monotonic()
        self._turn += 1
        msg_count = sum(len(m) for m in messages) if messages else 0
        logger.info("[Turn %d] 🧠 LLM 请求: model=%s, 消息数=%d", self._turn, model, msg_count)

        # 重置分项缓存（每次调用都重新统计）
        self._last_messages = []
        self._last_system_text = ""
        self._last_tools_text = ""

        # 记录最近一次调用的完整 messages（用于 token 分项统计）
        # LangChain 的 messages 参数是 list[list[BaseMessage]]（外层是 batch 维度）
        flat_messages: list = []
        if messages:
            for batch in messages:
                if batch:
                    flat_messages.extend(batch)
        self._last_messages = flat_messages

        # 合并所有 SystemMessage 文本（DeepAgents 可能拆成多个）
        system_parts: list[str] = []
        for m in flat_messages:
            if m.__class__.__name__ == "SystemMessage":
                system_parts.append(self._extract_message_text(m))
        self._last_system_text = "\n\n".join(p for p in system_parts if p)

        # 调试：定位 <agent_memory> 块的实际内容
        if self._turn == 1 and self._last_system_text:
            text = self._last_system_text
            start_marker = "<agent_memory>"
            end_marker = "</agent_memory>"
            start_idx = text.find(start_marker)
            end_idx = text.find(end_marker)
            if start_idx >= 0 and end_idx >= 0:
                memory_block = text[start_idx:end_idx + len(end_marker)]
                logger.debug(
                    "[Turn 1] 📋 <agent_memory> 块 (位置=%d-%d, length=%d):\n%s",
                    start_idx, end_idx, len(memory_block), memory_block,
                )

        # Anthropic 风格：system 可能不在 messages 里，而在 invocation_params["system"]
        if not self._last_system_text:
            params = kwargs.get("invocation_params") or {}
            sys_val = params.get("system") if isinstance(params, dict) else None
            if sys_val:
                self._last_system_text = (
                    sys_val if isinstance(sys_val, str)
                    else json.dumps(sys_val, ensure_ascii=False)
                )

        # 从多个可能位置提取 tools schema（不同 LangChain 版本字段位置不同）
        tools_to_serialize = None
        # 位置1：invocation_params["tools"]
        params = kwargs.get("invocation_params") or {}
        if isinstance(params, dict) and params.get("tools"):
            tools_to_serialize = params["tools"]
        # 位置2：kwargs["tools"]
        if not tools_to_serialize and kwargs.get("tools"):
            tools_to_serialize = kwargs["tools"]
        # 位置3：invocation_options["tools"]
        inv_opts = kwargs.get("invocation_options") or {}
        if not tools_to_serialize and isinstance(inv_opts, dict) and inv_opts.get("tools"):
            tools_to_serialize = inv_opts["tools"]

        if tools_to_serialize:
            self._last_tools_text = json.dumps(tools_to_serialize, ensure_ascii=False)

    def on_llm_start(self, serialized: dict, prompts: list, *, run_id: UUID, **kwargs: Any) -> None:
        self._timings[run_id] = time.monotonic()

    def on_llm_end(self, response, *, run_id: UUID, **kwargs: Any) -> None:
        elapsed = self._get_elapsed(run_id)
        llm_output = getattr(response, "llm_output", None) or {}
        usage = llm_output.get("token_usage") or llm_output.get("usage") or {}
        prompt_t = usage.get("prompt_tokens", 0)
        completion_t = usage.get("completion_tokens", 0)
        total_t = usage.get("total_tokens", 0)
        self._total_prompt_tokens += prompt_t
        self._total_completion_tokens += completion_t
        self._last_input_tokens = prompt_t
        self._last_output_tokens = completion_t
        token_info = f", tokens: {prompt_t}→{completion_t}(total={total_t})" if total_t else ""
        logger.info("[Turn %d] 🧠 LLM 响应: 耗时=%.1fs%s", self._turn, elapsed, token_info)

        # 从 LLMResult 的 generations 中提取最近一次调用的完整 messages
        # （AIMessage 上有 usage_metadata 标准字段）
        try:
            gens = getattr(response, "generations", None) or []
            if gens and gens[0]:
                last_gen = gens[0][0]
                last_msg = getattr(last_gen, "message", None)
                if last_msg is not None:
                    um = getattr(last_msg, "usage_metadata", None)
                    if um and not prompt_t:
                        # 优先使用 AIMessage.usage_metadata（更标准）
                        prompt_t = um.get("input_tokens", 0)
                        completion_t = um.get("output_tokens", 0)
                        total_t = um.get("total_tokens", 0)
                        self._last_input_tokens = prompt_t
                        self._last_output_tokens = completion_t
                        # 重新加总（避免重复计数）
                        self._total_prompt_tokens = (
                            self._total_prompt_tokens - usage.get("prompt_tokens", 0) + prompt_t
                        )
                        self._total_completion_tokens = (
                            self._total_completion_tokens - usage.get("completion_tokens", 0) + completion_t
                        )
        except Exception:  # noqa: BLE001
            pass

    def on_llm_error(self, error: Exception, *, run_id: UUID, **kwargs: Any) -> None:
        elapsed = self._get_elapsed(run_id)
        logger.error("[Turn %d] 🧠 LLM 错误: 耗时=%.1fs, error=%s", self._turn, elapsed, error)

    def on_llm_new_token(self, token: str, *, run_id: UUID, **kwargs: Any) -> None:
        pass

    # ── 工具相关 ────────────────────────────────────────────────

    def on_tool_start(
        self, serialized: dict, input_str: str, *, run_id: UUID, **kwargs: Any
    ) -> None:
        tool_name = serialized.get("name", "unknown")
        self._timings[run_id] = time.monotonic()
        self._tool_names[run_id] = tool_name
        self._tool_count += 1
        params_short = _truncate(input_str, 200)
        logger.info("[Turn %d] 🔧 调用工具: %s | 参数: %s", self._turn, tool_name, params_short)
        # 通过 sink 实时通知
        safe_call(
            self._sink, "notify_tool_start",
            self._turn, tool_name, params_short,
        )

    def on_tool_end(self, output: Any, *, run_id: UUID, **kwargs: Any) -> None:
        elapsed = self._get_elapsed(run_id)
        tool_name = self._tool_names.pop(run_id, "?")
        output_str = _truncate(output, 500)
        logger.info("[Turn %d] ✅ 工具结果: 耗时=%.1fs | %s", self._turn, elapsed, output_str)
        safe_call(
            self._sink, "notify_tool_end",
            self._turn, tool_name, _truncate(output, 300), elapsed,
        )

        # write_todos 特殊处理：解析任务进度并通过 sink 发送
        if tool_name == "write_todos":
            todos_text = self._format_todos(output)
            if todos_text:
                safe_call(
                    self._sink, "notify_tool_start",
                    self._turn, "📋 任务进度", todos_text,
                )

    def _format_todos(self, output: Any) -> str:
        """从 write_todos 的输出中解析任务列表，格式化为可读文本。"""
        try:
            # output 是 Command 对象，含 update={"todos": [...]}
            update = getattr(output, "update", None) or {}
            if isinstance(update, dict):
                todos = update.get("todos", [])
            elif isinstance(update, list):
                todos = update
            else:
                # 尝试从 output 本身解析
                todos = output if isinstance(output, list) else []

            if not todos:
                return ""

            status_icon = {
                "pending": "⬜",
                "in_progress": "🔄",
                "completed": "✅",
            }
            lines = []
            for i, todo in enumerate(todos, 1):
                if isinstance(todo, dict):
                    content = todo.get("content", "?")
                    status = todo.get("status", "pending")
                    icon = status_icon.get(status, "❓")
                    lines.append(f"{icon} {i}. {content} [{status}]")

            if not lines:
                return ""

            total = len(lines)
            done = sum(1 for t in todos if isinstance(t, dict) and t.get("status") == "completed")
            header = f"📋 任务进度 ({done}/{total})"
            return header + "\n" + "\n".join(lines)
        except Exception:  # noqa: BLE001
            return ""

    def on_tool_error(self, error: Exception, *, run_id: UUID, **kwargs: Any) -> None:
        elapsed = self._get_elapsed(run_id)
        tool_name = self._tool_names.pop(run_id, "?")
        logger.error("[Turn %d] ❌ 工具错误: 耗时=%.1fs | %s", self._turn, elapsed, error)
        safe_call(
            self._sink, "notify_tool_error",
            self._turn, tool_name, str(error), elapsed,
        )

    # ── Agent 决策 ──────────────────────────────────────────────

    def on_agent_action(self, action, *, run_id: UUID, **kwargs: Any) -> None:
        tool = getattr(action, "tool", "unknown")
        log = getattr(action, "log", "")
        logger.info("[Turn %d] 🤖 Agent 决策: 调用 %s | 思考: %s", self._turn, tool, _truncate(log, 200))

    def on_agent_finish(self, finish, *, run_id: UUID, **kwargs: Any) -> None:
        log = getattr(finish, "log", "")
        logger.info("[Turn %d] 🤖 Agent 完成: %s", self._turn, _truncate(log, 200) if log else "无日志")

    # ── 链路追踪 ────────────────────────────────────────────────

    def on_chain_start(
        self, serialized: dict | None, inputs: dict, *, run_id: UUID, **kwargs: Any
    ) -> None:
        self._timings[run_id] = time.monotonic()
        logger.debug("[Turn %d] ▶ 链路开始: %s", self._turn, (serialized or {}).get("name", "chain"))

    def on_chain_end(self, outputs: dict, *, run_id: UUID, **kwargs: Any) -> None:
        elapsed = self._get_elapsed(run_id)
        logger.debug("[Turn %d] ■ 链路结束: 耗时=%.1fs", self._turn, elapsed)

    def on_chain_error(self, error: Exception, *, run_id: UUID, **kwargs: Any) -> None:
        elapsed = self._get_elapsed(run_id)
        # Interrupt 是 LangGraph 的正常控制流机制（人工审批暂停），不是错误
        error_str = str(error)
        if "Interrupt(" in error_str or "GraphInterrupt" in type(error).__name__:
            logger.info("[Turn %d] ■ 链路暂停（等待人工审批）", self._turn)
            return
        logger.error("[Turn %d] ■ 链路错误: 耗时=%.1fs | %s", self._turn, elapsed, error)

    # ── 重试 ────────────────────────────────────────────────────

    def on_retry(self, retry_state, *, run_id: UUID, **kwargs: Any) -> None:
        attempt = getattr(retry_state, "attempt_number", "?")
        logger.warning("[Turn %d] 🔄 重试: 第 %s 次", self._turn, attempt)

    # ── 辅助 ────────────────────────────────────────────────────

    def _get_elapsed(self, run_id: UUID) -> float:
        start = self._timings.pop(run_id, None)
        return time.monotonic() - start if start else 0.0

    def summary(self) -> str:
        """生成统计摘要，并通过 sink 发送。"""
        total_tokens = self._total_prompt_tokens + self._total_completion_tokens
        total_elapsed = time.monotonic() - self._start_time

        ctx_info = self._context_usage_text()

        text = (
            f"📊 执行统计\n"
            f"🔄 Turn: {self._turn}\n"
            f"🤖 模型: {self._model_name}\n"
            f"⏱️ 总耗时: {total_elapsed:.1f}s\n"
            f"📥 Token 输入: {self._total_prompt_tokens}\n"
            f"📤 Token 输出: {self._total_completion_tokens}\n"
            f"🎯 Token 合计: {total_tokens}\n"
            f"{ctx_info}"
        )
        # 通过 sink 发送摘要
        safe_call(self._sink, "notify_summary", text)
        return text

    def _context_usage_text(self) -> str:
        """返回上下文窗口各部分用量的文字描述。

        设计思路：总量以 API 实测的 input_tokens 为准（最准确），
        分项用 tiktoken 本地估算计算占比，剩余部分作为"其他开销"，
        避免分项之和与总量对不上的尴尬。
        """
        if not self._last_messages and not self._last_system_text and not self._last_tools_text:
            return ""

        # 分项估算（tiktoken）
        system_tokens = self._count_tokens(self._last_system_text)
        tools_tokens = self._count_tokens(self._last_tools_text)

        messages_tokens = 0
        msg_count = 0
        for m in self._last_messages:
            if m.__class__.__name__ == "SystemMessage":
                continue
            msg_count += 1
            text = self._extract_message_text(m)
            messages_tokens += self._count_tokens(text)

        # 总量：优先用 API 实测；无实测时退化为本地估算之和
        total = self._last_input_tokens or (system_tokens + tools_tokens + messages_tokens)

        # 其他开销 = 总量 - 三项已知
        other_tokens = max(0, total - system_tokens - tools_tokens - messages_tokens)

        # 占比（相对总量）
        def pct(n: int) -> str:
            return f"{n * 100 / total:5.1f}%" if total else "  -  "

        # 占比（相对上下文窗口）
        window_pct = (
            f"{total * 100 / self._context_window:5.1f}%"
            if self._context_window
            else "  -  "
        )

        lines = [
            "📊 上下文用量:",
            f"  🟢 系统提示词:      {system_tokens:>6,} tokens  ({pct(system_tokens)})",
            f"  🟡 工具及子智能体:  {tools_tokens:>6,} tokens  ({pct(tools_tokens)})",
            f"  🟣 对话消息:        {messages_tokens:>6,} tokens  ({pct(messages_tokens)})  ({msg_count} 条)",
            f"  ⚪ 其他开销:        {other_tokens:>6,} tokens  ({pct(other_tokens)})",
            f"  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"  📐 当前上下文:      {total:>6,} / {self._context_window:,} tokens  ({window_pct})",
        ]
        return "\n".join(lines)
