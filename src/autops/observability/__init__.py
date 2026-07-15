"""可观测性模块 — Agent 执行过程的监控、统计与回调。

提供与具体 channel 无关的通用回调处理器，各 channel（CLI / 飞书 / API）
只需实现 EventSink 协议即可接入。
"""

from autops.observability.handler import AgentObservabilityHandler
from autops.observability.sink import EventSink, NullEventSink

__all__ = ["AgentObservabilityHandler", "EventSink", "NullEventSink"]
