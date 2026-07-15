"""事件输出协议 — channels 实现此协议即可接入可观测性回调。

设计为"鸭子类型"协议，无需继承。每个 channel 把自己的消息发送能力
适配成 EventSink 的几个方法即可：
- notify_tool_start / notify_tool_end / notify_tool_error：工具执行过程的实时通知
- notify_summary：执行结束后的统计摘要

未实现的方法会被 Handler 静默忽略（用 getattr + hasattr 兜底）。
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class EventSink(Protocol):
    """事件输出协议 — channels 实现以接收可观测性事件。"""

    def notify_tool_start(self, turn: int, tool_name: str, params: str) -> None:
        """工具开始执行通知。"""
        ...

    def notify_tool_end(self, turn: int, tool_name: str, output: str, elapsed: float) -> None:
        """工具执行完成通知。"""
        ...

    def notify_tool_error(self, turn: int, tool_name: str, error: str, elapsed: float) -> None:
        """工具执行错误通知。"""
        ...

    def notify_summary(self, summary: str) -> None:
        """执行结束后的统计摘要。"""
        ...


class NullEventSink:
    """空实现 — 不发送任何事件，用于不需要实时通知的场景（如 CLI）。"""

    def notify_tool_start(self, turn: int, tool_name: str, params: str) -> None:
        pass

    def notify_tool_end(self, turn: int, tool_name: str, output: str, elapsed: float) -> None:
        pass

    def notify_tool_error(self, turn: int, tool_name: str, error: str, elapsed: float) -> None:
        pass

    def notify_summary(self, summary: str) -> None:
        pass


def safe_call(sink: Any, method: str, *args: Any, **kwargs: Any) -> None:
    """安全调用 sink 方法，异常静默（避免影响 Agent 主流程）。"""
    fn = getattr(sink, method, None)
    if fn is None:
        return
    try:
        fn(*args, **kwargs)
    except Exception:  # noqa: BLE001
        # sink 失败不应影响 Agent 执行
        pass
