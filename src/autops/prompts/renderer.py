"""Jinja2 模板渲染器 — 统一加载和渲染 .j2 提示词模板。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

# 模板目录：prompts/templates/
_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

# 全局 Jinja2 环境（禁用自动转义，因为提示词是纯文本而非 HTML）
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(default=False),
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=False,
)


def render_prompt(template_name: str, **context: Any) -> str:
    """渲染指定的 Jinja2 模板。

    Args:
        template_name: 模板文件名（如 "main_agent.j2"）。
        **context: 传递给模板的变量。

    Returns:
        渲染后的提示词字符串。

    Raises:
        jinja2.TemplateNotFound: 模板文件不存在时抛出。
    """
    template = _env.get_template(template_name)
    return template.render(**context)


def list_templates() -> list[str]:
    """列出所有可用的模板文件名。

    Returns:
        模板文件名列表（如 ["main_agent.j2"]）。
    """
    return sorted(
        f.name for f in _TEMPLATES_DIR.glob("*.j2")
    )
