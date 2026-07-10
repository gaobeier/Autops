"""Prompts 模块 — 系统提示词与 Jinja2 模板管理。

所有提示词使用 Jinja2 模板（.j2）定义，存放在 templates/ 目录下：
- templates/main_agent.j2 — 主 Agent 系统提示词
- renderer.py — 模板加载与渲染引擎
- system.py — 提示词构建函数

使用方式：
    from autops.prompts.system import get_main_agent_prompt
    prompt = get_main_agent_prompt()
"""

from autops.prompts.renderer import list_templates, render_prompt
from autops.prompts.system import get_main_agent_prompt

__all__ = ["get_main_agent_prompt", "render_prompt", "list_templates"]
