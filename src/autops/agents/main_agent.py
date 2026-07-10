"""主智能体定义 — 使用 Deepagents 框架创建。"""

from __future__ import annotations

import logging
from pathlib import Path

from deepagents import create_deep_agent
from deepagents.backends import LocalShellBackend
from langgraph.checkpoint.memory import MemorySaver

from autops.config.settings import config
from autops.llm.client import create_llm
from autops.prompts.system import get_main_agent_prompt

logger = logging.getLogger(__name__)

# 全局 checkpointer 单例（所有会话共享，通过 thread_id 区分）
_checkpointer: MemorySaver | None = None


def _get_workspace() -> Path:
    """获取 Agent 工作目录。

    优先使用 config.yaml 中 agent.workspace 配置，
    未配置则使用项目根目录（config.yaml 所在目录的上一级）。
    """
    workspace = config.agent.workspace
    if workspace:
        p = Path(workspace).resolve()
    else:
        p = Path(__file__).resolve().parents[3]
    p.mkdir(parents=True, exist_ok=True)
    return p


def _build_backend(workspace: Path) -> LocalShellBackend:
    """构建受限的本地 Shell 后端。

    将文件系统和 Shell 执行限制在 workspace 目录内。
    使用 virtual_mode=True 使路径相对于 root_dir（/ = workspace 根）。
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


def create_main_agent(tools: list | None = None) -> object:
    """创建主 Agent。

    通过 LocalShellBackend(root_dir, virtual_mode=True) 将 Agent 的
    文件操作限制在 workspace 目录内（/ = workspace 根）。

    通过 MemorySaver checkpointer 自动管理多轮对话状态，
    调用时通过 config={"thread_id": session_id} 区分不同会话，
    无需手动维护消息历史。

    Args:
        tools: 自定义工具列表，默认为空（仅使用 Deepagents 内置工具）。

    Returns:
        编译后的 Deep Agent 实例，可通过 .invoke() 或 .stream() 调用。
    """
    workspace = _get_workspace()
    logger.info("Agent 工作目录: %s", workspace)

    llm = create_llm()
    system_prompt = get_main_agent_prompt()
    backend = _build_backend(workspace)
    checkpointer = _get_checkpointer()

    return create_deep_agent(
        model=llm,
        tools=tools or [],
        system_prompt=system_prompt,
        backend=backend,
        checkpointer=checkpointer,
    )
