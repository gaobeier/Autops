"""命令安全策略 — 三级风险检测。

高危（硬编码）：直接拒绝，不执行
危险（可配置）：触发人工审批
低风险（默认）：直接放行
"""

from __future__ import annotations

import re
import shlex
from typing import Any

# ── 高危命令（硬编码，直接拒绝，不可配置）──
# 这些命令无论什么情况都不允许执行
CRITICAL_COMMAND_PATTERNS: list[str] = [
    r"\brm\s+(-\w*\s+)*(/|~|\*|/\*|/\s)",  # rm -rf /、rm -rf ~、rm -rf *
    r"\brm\s+(-\w*\s+)*\.\s*$",              # rm -rf .
    r"\brm\s+(-\w*\s+)*\.\.",               # rm -rf ..
    r"\bdd\b.*\bof\s*=\s*/dev/sd[a-z]",     # dd 写裸盘
    r":\(\)\s*\{\s*:\|:&\s*\}\s*;",         # fork bomb
    r"\bmkfs\b.*\b/dev/sd[a-z]",            # mkfs 格式化磁盘
    r">\s*/dev/sd[a-z]",                    # 重定向到裸盘
    r"\bshred\b.*\b/dev/sd[a-z]",           # shred 裸盘
]

# 高危路径（硬编码，直接拒绝）
CRITICAL_PATH_PATTERNS: list[str] = [
    r"/dev/sd[a-z]",          # 裸磁盘设备
    r"/dev/(nvme|vd)[a-z]+", # NVMe/virtio 磁盘
]

# 编译高危正则
_COMPILED_CRITICAL: list[re.Pattern] = [
    re.compile(pat, re.IGNORECASE) for pat in CRITICAL_COMMAND_PATTERNS + CRITICAL_PATH_PATTERNS
]

# ── 允许的系统路径前缀（不视为越界）──
_ALLOWED_SYSTEM_PATHS = (
    "/bin", "/usr", "/lib", "/lib64", "/lib32",
    "/dev/null", "/dev/zero", "/dev/urandom", "/dev/random",
    "/dev/stdin", "/dev/stdout", "/dev/stderr",
    "/tmp",
    "/proc/self",
    "/etc/hostname", "/etc/resolv.conf", "/etc/ssl", "/etc/alternatives",
)


def _extract_paths(command: str) -> list[str]:
    """从命令中提取所有以 / 开头的路径。"""
    paths: list[str] = []
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        return re.findall(r"(?:^|\s)(/\S+)", command)

    for token in tokens:
        parts = token.split("=", 1)
        for part in parts:
            if part.startswith("/"):
                clean = part.strip("'\"")
                if clean.startswith("/"):
                    paths.append(clean)
    return paths


def _is_path_outside_allowed(path: str) -> bool:
    """判断路径是否在允许的系统路径外（即 workspace 外）。"""
    for allowed in _ALLOWED_SYSTEM_PATHS:
        if path == allowed or path.startswith(allowed + "/"):
            return False
    return True


def assess_command(
    command: str,
    dangerous_commands: list[str] | None = None,
    dangerous_paths: list[str] | None = None,
) -> tuple[str, str]:
    """评估命令风险等级。

    Args:
        command: shell 命令字符串。
        dangerous_commands: 危险命令正则列表（来自 config.yaml）。
        dangerous_paths: 危险路径正则列表（来自 config.yaml）。

    Returns:
        (风险等级, 原因) 元组。
        风险等级: "critical" | "dangerous" | "safe"
    """
    if not command or not command.strip():
        return "safe", ""

    normalized = " ".join(command.split())

    # 1. 检查高危命令/路径（硬编码）
    for pattern in _COMPILED_CRITICAL:
        if pattern.search(normalized):
            return "critical", f"高危操作: {pattern.pattern}"

    # 2. 检查危险命令（config.yaml 可配置）
    if dangerous_commands:
        for pat_str in dangerous_commands:
            try:
                if re.search(pat_str, normalized, re.IGNORECASE):
                    return "dangerous", f"危险命令: {pat_str}"
            except re.error:
                continue

    # 3. 检查危险路径（config.yaml 可配置）
    paths = _extract_paths(normalized)
    if dangerous_paths:
        for path in paths:
            for pat_str in dangerous_paths:
                try:
                    if re.search(pat_str, path, re.IGNORECASE):
                        return "dangerous", f"危险路径: {path} (匹配: {pat_str})"
                except re.error:
                    continue

    # 4. 检查 workspace 外路径（默认危险）
    for path in paths:
        if _is_path_outside_allowed(path):
            return "dangerous", f"访问 workspace 外路径: {path}"

    return "safe", ""


def is_critical_command(command: str) -> tuple[bool, str]:
    """判断命令是否高危（直接拒绝）。

    Returns:
        (是否高危, 原因) 元组。
    """
    level, reason = assess_command(command)
    return level == "critical", reason


def should_interrupt_execute(request: Any) -> bool:
    """InterruptOnConfig.when 谓词：判断 execute 工具调用是否需要审批。

    高危命令不走这里（被中间件拦截），这里只处理"危险"级别。

    Returns:
        True 表示需要审批，False 表示放行。
    """
    tool_call = getattr(request, "tool_call", None) or {}
    if isinstance(tool_call, dict):
        args = tool_call.get("args", {})
    else:
        args = {}
    command = args.get("command", "") if isinstance(args, dict) else ""

    # 加载 config 中的危险命令/路径配置
    from autops.config.settings import config
    safety = config.agent.safety

    level, reason = assess_command(
        command,
        dangerous_commands=safety.dangerous_commands,
        dangerous_paths=safety.dangerous_paths,
    )

    if level == "dangerous":
        import logging
        logging.getLogger(__name__).info("命令需审批: %r, 原因: %s", command, reason)
        return True

    return False
