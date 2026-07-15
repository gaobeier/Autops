"""主智能体定义 — 使用 Deepagents 框架创建。"""

from __future__ import annotations

import logging
from pathlib import Path

from deepagents import create_deep_agent
from deepagents.backends import LocalShellBackend
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph.state import CompiledStateGraph

from autops.config.settings import config
from autops.llm.client import create_llm
from autops.middleware import AlwaysReloadMemoryMiddleware
from autops.prompts.system import get_main_agent_prompt
from autops.tools import internet_search

logger = logging.getLogger(__name__)

# 全局 checkpointer 单例（所有会话共享，通过 thread_id 区分）
_checkpointer: PostgresSaver | None = None


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

# 长期记忆目录（workspace/memory），存放 AGENTS.md 等记忆文件
_MEMORY_DIR = _WORKSPACE / "memory"
_MEMORY_DIR.mkdir(parents=True, exist_ok=True)
logger.info("Agent 记忆目录: %s", _MEMORY_DIR)


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


def _get_checkpointer() -> PostgresSaver:
    """获取全局 checkpointer 单例。

    使用 PostgresSaver（PostgreSQL 持久化存储），进程重启后不丢失。
    首次调用时建立连接并自动建表。
    使用 autops 数据库的 public schema。
    """
    global _checkpointer
    if _checkpointer is None:
        pg = config.postgres
        conn_str = (
            f"host={pg.host} port={pg.port} user={pg.user} "
            f"password={pg.password} dbname={pg.database}"
        )
        from psycopg import Connection
        from psycopg.rows import dict_row

        conn = Connection.connect(
            conn_str,
            autocommit=True,
            prepare_threshold=0,
            row_factory=dict_row,
            options="-c search_path=public",
        )

        _checkpointer = PostgresSaver(conn)
        _checkpointer.setup()  # 在 public schema 中创建所需的表
        logger.info(
            "Checkpointer 已初始化 (PostgresSaver: %s:%d/%s, schema=public)",
            pg.host, pg.port, pg.database,
        )
    return _checkpointer


def _build_memory_middleware(user_id: str | None = None) -> list:
    """构建长期记忆中间件。

    按 user_id 隔离 AGENTS.md 文件路径：
    - user_id 有值：/memory/{user_id}/AGENTS.md
    - user_id 为 None：/memory/AGENTS.md（全局共享）

    文件存在时返回包含 AlwaysReloadMemoryMiddleware 的列表，
    不存在时返回空列表（不加载记忆）。

    注意：backend 使用 virtual_mode=True，路径需以 `/` 开头
    （相对 workspace 的虚拟绝对路径）。

    Args:
        user_id: 用户标识（如飞书 open_id）。

    Returns:
        中间件列表（可能为空）。
    """
    if user_id:
        memory_dir = _MEMORY_DIR / user_id
        memory_dir.mkdir(parents=True, exist_ok=True)
        memory_path = f"/memory/{user_id}/AGENTS.md"
    else:
        memory_path = "/memory/AGENTS.md"

    real_path = _WORKSPACE / memory_path.lstrip("/")
    if not real_path.exists():
        logger.info(
            "长期记忆文件不存在，跳过加载: user_id=%s, memory_path=%s",
            user_id or "(global)", memory_path,
        )
        return []

    logger.info(
        "配置长期记忆中间件: user_id=%s, memory_path=%s, size=%dB",
        user_id or "(global)", memory_path, real_path.stat().st_size,
    )
    return [
        AlwaysReloadMemoryMiddleware(
            backend=_build_backend(_WORKSPACE),
            sources=[memory_path],
        )
    ]


def _build_agent(user_id: str | None = None) -> CompiledStateGraph:
    """构建 Agent 实例（内部函数，供 channels 调用）。

    Args:
        user_id: 用户标识（如飞书 open_id），用于隔离不同用户的长期记忆。
                  为 None 时使用全局共享记忆。

    Returns:
        编译后的 Deep Agent 实例。
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
        middleware=_build_memory_middleware(user_id),
    )


def create_main_agent() -> CompiledStateGraph:
    """创建主 Agent（LangGraph dev 工厂入口，无参数）。

    通过 LocalShellBackend(root_dir, virtual_mode=True) 将 Agent 的
    文件操作限制在 workspace 目录内，Agent 使用真实绝对路径操作文件。

    通过 PostgresSaver checkpointer 持久化多轮对话状态，
    调用时通过 config={"thread_id": session_id} 区分不同会话，
    进程重启后对话历史不丢失。

    通过 interrupt_on 配置人工审批：edit_file / execute
    等危险操作在执行前暂停，等待人工确认后才继续。

    通过 middleware 配置长期记忆：加载 workspace/memory/AGENTS.md（全局共享），
    其内容会被注入 system prompt 的 <agent_memory> 块，
    使用 AlwaysReloadMemoryMiddleware 每次 invoke 都重新读取，
    Agent 可通过 write_file 工具更新此文件，实现跨会话记忆。

    Returns:
        编译后的 Deep Agent 实例，可通过 .invoke() 或 .stream() 调用。
    """
    return _build_agent(user_id=None)
