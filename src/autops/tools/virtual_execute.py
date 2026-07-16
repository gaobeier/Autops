"""自定义工具集 — 覆盖 Deepagents 默认工具行为。"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Annotated, Any

from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool, InjectedToolCallId, StructuredTool
from langgraph.types import Command
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ExecuteInput(BaseModel):
    """execute 工具的输入参数。"""

    command: str
    timeout: int | None = None


def create_virtual_execute_tool(workspace: Path) -> BaseTool:
    """创建虚拟路径版的 execute 工具。

    与 Deepagents 默认 execute 工具的区别：
    - 命令在 workspace 目录下执行（cwd=workspace）
    - 输出中的真实路径被替换为虚拟路径（/ = workspace 根）
    - Agent 看到的 pwd 是 /，ls 看到的是 workspace 下的文件

    Args:
        workspace: 用户工作空间路径（backend 的 root_dir）。

    Returns:
        自定义 execute 工具。
    """
    workspace_resolved = workspace.resolve()
    workspace_str = str(workspace_resolved)
    workspace_posix = workspace_resolved.as_posix()
    workspace_msys = "/" + workspace_posix.replace(":", "").lower()

    def _sanitize_output(text: str) -> str:
        """将输出中的真实路径替换为虚拟路径。"""
        result = text
        result = result.replace(workspace_str, "/")
        result = result.replace(workspace_posix, "/")
        result = result.replace(workspace_msys, "/")
        return result

    def _execute(
        command: str,
        timeout: int | None = None,
        tool_call_id: Annotated[str, InjectedToolCallId] = "",
    ) -> Any:
        """在虚拟工作空间中执行 shell 命令。

        命令在 workspace 目录下执行，输出中的真实路径被隐藏。
        Agent 看到的是虚拟路径（/ = workspace 根）。
        """
        if not command or not command.strip():
            return Command(update={
                "messages": [ToolMessage(
                    content="Error: Command must be a non-empty string.",
                    tool_call_id=tool_call_id,
                )]
            })

        effective_timeout = timeout or 120

        try:
            result = subprocess.run(
                command,
                check=False,
                shell=True,
                capture_output=True,
                stdin=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=effective_timeout,
                cwd=workspace_str,
            )

            output_parts: list[str] = []
            if result.stdout:
                output_parts.append(result.stdout)
            if result.stderr:
                for line in result.stderr.strip().split("\n"):
                    output_parts.append(f"[stderr] {line}")

            output = "\n".join(output_parts) if output_parts else "<no output>"
            output = _sanitize_output(output)

            if len(output) > 100_000:
                output = output[:100_000] + "\n\n... Output truncated at 100000 bytes."

            output += f"\n\n[Command exited with code {result.returncode}]"

            return Command(update={
                "messages": [ToolMessage(content=output, tool_call_id=tool_call_id)]
            })

        except subprocess.TimeoutExpired:
            return Command(update={
                "messages": [ToolMessage(
                    content=f"Error: Command timed out after {effective_timeout}s.",
                    tool_call_id=tool_call_id,
                )]
            })
        except Exception as e:  # noqa: BLE001
            return Command(update={
                "messages": [ToolMessage(
                    content=f"Error: {e}",
                    tool_call_id=tool_call_id,
                )]
            })

    return StructuredTool.from_function(
        name="execute",
        description=(
            "Executes a shell command in the workspace. "
            "The working directory is the workspace root (/). "
            "Use this for running commands like ls, cat, grep, find, etc. "
            "Avoid using this for file operations that can be done with read_file, write_file, or edit_file tools."
        ),
        func=_execute,
        args_schema=ExecuteInput,
        infer_schema=False,
    )
