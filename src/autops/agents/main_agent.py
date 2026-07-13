"""主智能体定义 — 使用 Deepagents 框架创建。"""

from __future__ import annotations

import logging
from pathlib import Path

from deepagents import create_deep_agent
from deepagents.backends import LocalShellBackend
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.state import CompiledStateGraph

from autops.config.settings import config
from autops.llm.client import create_llm
from autops.prompts.system import get_main_agent_prompt
from autops.tools import internet_search

logger = logging.getLogger(__name__)

# 全局 checkpointer 单例（所有会话共享，通过 thread_id 区分）
_checkpointer: MemorySaver | None = None


def _resolve_workspace() -> Path:
    """解析 Agent 工作目录路径（不做 I/O）。

    使用 config.yaml 中 agent.workspace 配置，
    未配置则默认为 ./workspace（相对于项目根目录）。
    """
    return Path(config.agent.workspace).resolve()


# 模块级别预计算 workspace 并创建目录。
# 模块导入在 LangGraph dev 的线程池中执行，允许阻塞 I/O；
# 而工厂函数 create_main_agent 在事件循环中执行，不能有阻塞调用。
_WORKSPACE = _resolve_workspace()
_WORKSPACE.mkdir(parents=True, exist_ok=True)
logger.info("Agent 工作目录: %s", _WORKSPACE)


def _build_backend(workspace: Path) -> LocalShellBackend:
    """构建受限的本地 Shell 后端。

    将文件系统和 Shell 执行限制在 workspace 目录内。
    Agent 使用真实绝对路径操作文件（如 /opt/Autops/workspace/test.txt），
    backend 确保所有路径不会逃逸出 root_dir。
    """
    return LocalShellBackend(
        root_dir=str(workspace),
        virtual_mode=True,
        timeout=120,
        max_output_bytes=100_000,
        inherit_env=True,
    )


def _get_checkpointer() -> MemorySaver:
    """获取全局 checkpointer 单例。

    使用 MemorySaver（内存存储），进程重启后丢失。
    如需持久化，可替换为 SqliteSaver 或 PostgresSaver。
    """
    global _checkpointer
    if _checkpointer is None:
        _checkpointer = MemorySaver()
        logger.info("Checkpointer 已初始化 (MemorySaver)")
    return _checkpointer


def create_main_agent() -> CompiledStateGraph:
    """创建主 Agent。

    通过 LocalShellBackend(root_dir, virtual_mode=False) 将 Agent 的
    文件操作限制在 workspace 目录内，Agent 使用真实绝对路径操作文件。

    通过 MemorySaver checkpointer 自动管理多轮对话状态，
    调用时通过 config={"thread_id": session_id} 区分不同会话，
    无需手动维护消息历史。

    通过 interrupt_on 配置人工审批：edit_file / write_file / execute
    等危险操作在执行前暂停，等待人工确认后才继续。

    注册 internet_search 自定义工具，提供互联网搜索能力。

    Returns:
        编译后的 Deep Agent 实例，可通过 .invoke() 或 .stream() 调用。
    """
    return create_deep_agent(
        model=create_llm(),
        tools=[internet_search],
        system_prompt=get_main_agent_prompt(),
        backend=_build_backend(_WORKSPACE),
        checkpointer=_get_checkpointer(),
        interrupt_on={
            "edit_file": True,
            "execute": True,
        },
    )
