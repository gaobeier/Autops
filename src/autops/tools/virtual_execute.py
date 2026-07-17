"""自定义 execute 工具 — 限制命令在 workspace 内执行。

通过 cwd=workspace + 路径预处理实现软隔离：
- 命令在 workspace 目录下执行
- 命令中的绝对路径 /file 被转换为 ./file（相对 workspace）
- 输出中的真实路径被替换为 . （隐藏宿主机路径）
- /bin、/usr、/lib 等系统路径保持不变（保证命令可用）
"""

from __future__ import annotations

import logging
import re
import shlex
import subprocess
from pathlib import Path

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# 不需要转换的系统路径前缀（保证 ls /bin、which cat 等命令正常工作）
_SYSTEM_PREFIXES = (
    "/bin", "/usr", "/lib", "/lib64",
    "/dev", "/proc", "/sys", "/tmp",
    "/etc/hostname", "/etc/resolv.conf", "/etc/ssl", "/etc/alternatives",
)


class ExecuteInput(BaseModel):
    """execute 工具的输入参数。"""

    command: str = Field(description="Shell command to execute in the workspace")
    timeout: int | None = Field(
        default=None,
        description="Optional timeout in seconds. Default 120.",
    )


def _rewrite_command(command: str) -> str:
    """将命令中的绝对路径 /file 转换为相对路径 ./file。

    保留系统路径（/bin、/usr 等）不变。
    使用 shlex 解析命令，对每个 token 判断是否需要转换。

    对于无法用 shlex 解析的复杂命令（含管道、重定向等），
    回退到正则替换：把行首或空格后的 /xxx 转换为 ./xxx。
    """
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        # shlex 解析失败（如不匹配的引号），用正则兜底
        return _rewrite_command_regex(command)

    rewritten: list[str] = []
    for token in tokens:
        rewritten.append(_rewrite_token(token))

    # 用 shlex 重新组合（自动处理引号）
    return " ".join(shlex.quote(t) if _needs_quote(t) else t for t in rewritten)


def _needs_quote(token: str) -> bool:
    """判断 token 是否需要引号包裹。"""
    # 含特殊字符的需要引号
    return any(c in token for c in " \t\"'\\$`|&;<>(){}[]")


def _rewrite_token(token: str) -> str:
    """转换单个 token 中的绝对路径为相对路径。"""
    if not token.startswith("/"):
        return token

    # 系统路径不转换
    if token.startswith(_SYSTEM_PREFIXES):
        return token

    # /file → ./file
    return "./" + token[1:]


def _rewrite_command_regex(command: str) -> str:
    """正则兜底：把非系统路径的 /xxx 转换为 ./xxx。"""
    # 匹配：行首或空格后的 /，后面跟非系统路径
    def replace(match: re.Match) -> str:
        prefix = match.group(1)  # 行首或空格
        path = match.group(2)   # /xxx
        # 系统路径不转换
        if path.startswith(_SYSTEM_PREFIXES):
            return prefix + path
        return prefix + "./" + path[1:]

    return re.sub(r"(^|\s)(/\S+)", replace, command)


def create_virtual_execute_tool(workspace: Path) -> BaseTool:
    """创建虚拟路径版的 execute 工具。

    与 Deepagents 默认 execute 工具的区别：
    - 命令在 workspace 目录下执行（cwd=workspace）
    - 命令中的绝对路径 /file 被转换为 ./file
    - 输出中的真实路径被替换为 . （隐藏宿主机路径）

    Args:
        workspace: 用户工作空间路径。

    Returns:
        自定义 execute 工具。
    """
    workspace_resolved = workspace.resolve()
    workspace_str = str(workspace_resolved)
    workspace_posix = workspace_resolved.as_posix()
    workspace_msys = "/" + workspace_posix.replace(":", "").lower()

    def _sanitize_output(text: str) -> str:
        """将输出中的真实路径替换为 . （当前目录）。"""
        result = text
        result = result.replace(workspace_str, ".")
        result = result.replace(workspace_posix, ".")
        result = result.replace(workspace_msys, ".")
        return result

    def _execute(
        command: str,
        timeout: int | None = None,
    ) -> str:
        """在 workspace 中执行 shell 命令。

        命令在 workspace 目录下执行，绝对路径被自动转换为相对路径。
        """
        if not command or not command.strip():
            return "Error: Command must be a non-empty string."

        effective_timeout = timeout or 120

        # 预处理命令：/file → ./file
        rewritten = _rewrite_command(command)
        if rewritten != command:
            logger.debug("命令重写: %r → %r", command, rewritten)

        try:
            result = subprocess.run(
                rewritten,
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
                output_parts.append(result.stdout.rstrip())
            if result.stderr:
                for line in result.stderr.strip().split("\n"):
                    output_parts.append(f"[stderr] {line}")

            output = "\n".join(output_parts) if output_parts else "<no output>"
            output = _sanitize_output(output)

            if len(output) > 100_000:
                output = output[:100_000] + "\n\n... Output truncated at 100000 bytes."

            # 退出码非 0 时追加提示
            if result.returncode != 0:
                output += f"\n\n[Command exited with code {result.returncode}]"

            return output

        except subprocess.TimeoutExpired:
            return f"Error: Command timed out after {effective_timeout}s."
        except Exception as e:  # noqa: BLE001
            return f"Error: {e}"

    return StructuredTool.from_function(
        name="execute",
        description=(
            "Executes a shell command in the workspace. "
            "The working directory is the workspace root. "
            "Use relative paths (e.g. `cat file.txt`, `ls`, `grep error app.log`) "
            "or absolute paths (e.g. `cat /file.txt` — auto-converted to `./file.txt`). "
            "Use this for running commands like ls, cat, grep, find, etc. "
            "Avoid using this for file operations that can be done with read_file, write_file, or edit_file tools."
        ),
        func=_execute,
        args_schema=ExecuteInput,
    )
