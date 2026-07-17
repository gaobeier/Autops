"""Tools 模块 — SRE/DevOps 运维工具集。

本模块提供 Agent 可调用的自定义工具：
- search：互联网搜索（基于 Tavily API）
- dangerous_commands：命令安全策略（三级风险检测）
- virtual_execute：受限的 Shell 命令执行（可选，使用 bwrap 沙箱）
"""

from autops.tools.dangerous_commands import (
    assess_command,
    is_critical_command,
    should_interrupt_execute,
)
from autops.tools.search import internet_search
from autops.tools.virtual_execute import create_virtual_execute_tool

__all__ = [
    "internet_search",
    "create_virtual_execute_tool",
    "assess_command",
    "is_critical_command",
    "should_interrupt_execute",
]
