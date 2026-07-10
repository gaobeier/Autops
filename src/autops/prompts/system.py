"""系统提示词 — 通过 Jinja2 模板渲染。

所有提示词模板存放在 templates/ 目录下的 .j2 文件中，
通过 renderer.render_prompt() 加载并渲染。
"""

from __future__ import annotations

from autops.prompts.renderer import render_prompt

# 主 Agent 默认变量
_MAIN_AGENT_CONTEXT = {
    "agent_name": "Autops",
    "capabilities": [
        "系统监控与故障排查（CPU、内存、磁盘、网络）",
        "日志分析与问题定位",
        "容器管理（Docker）",
        "网络诊断（ping、端口检测、DNS）",
        "Git 仓库操作",
        "Shell 命令执行",
    ],
    "principles": [
        "理解用户意图后，选择合适的工具执行任务",
        "对工具返回的结果进行分析和总结",
        "如果需要多个步骤，逐步执行并说明每步操作",
        "遇到危险操作（如删除文件、重启服务）时，先向用户确认",
        "用简洁清晰的中文回复",
    ],
}


def get_main_agent_prompt(**overrides: object) -> str:
    """获取主 Agent 系统提示词。

    Args:
        **overrides: 覆盖默认模板变量（如 agent_name、capabilities）。

    Returns:
        渲染后的系统提示词字符串。
    """
    context = {**_MAIN_AGENT_CONTEXT, **overrides}
    return render_prompt("main_agent.j2", **context)
