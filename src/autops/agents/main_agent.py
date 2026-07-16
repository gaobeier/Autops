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

# 会话根目录（所有用户的 session 数据存放于此）
_SESSION_ROOT = Path(config.agent.workspace).resolve() / "session"
_SESSION_ROOT.mkdir(parents=True, exist_ok=True)
logger.info("会话根目录: %s", _SESSION_ROOT)


def _get_user_workspace(user_id: str) -> Path:
    """获取用户工作空间路径。

    目录结构: session/{user_id}/workspace/

    Args:
        user_id: 用户标识（如飞书 open_id）。

    Returns:
        用户工作空间目录路径（已创建）。
    """
    ws = _SESSION_ROOT / user_id / "workspace"
    ws.mkdir(parents=True, exist_ok=True)
    return ws


def _build_backend(workspace: Path) -> LocalShellBackend:
    """构建受限的本地 Shell 后端。

    将文件系统和 Shell 执行限制在指定 workspace 目录内。
    Agent 使用真实绝对路径操作文件，backend 确保路径不逃逸出 root_dir。
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
        _checkpointer.setup()
        logger.info(
            "Checkpointer 已初始化 (PostgresSaver: %s:%d/%s, schema=public)",
            pg.host, pg.port, pg.database,
        )
    return _checkpointer


def _build_memory_middleware(workspace: Path, user_id: str | None = None) -> list:
    """构建长期记忆中间件。

    记忆文件路径: workspace/memory/AGENTS.md（在用户 workspace 内）

    Args:
        workspace: 用户工作空间路径。
        user_id: 用户标识（仅用于日志）。

    Returns:
        中间件列表（可能为空）。
    """
    memory_dir = workspace / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    memory_path = "/memory/AGENTS.md"

    real_path = workspace / memory_path.lstrip("/")
    if not real_path.exists():
        logger.info(
            "长期记忆文件不存在，跳过加载: user_id=%s, path=%s",
            user_id or "(global)", real_path,
        )
        return []

    logger.info(
        "配置长期记忆: user_id=%s, path=%s, size=%dB",
        user_id or "(global)", real_path, real_path.stat().st_size,
    )
    return [
        AlwaysReloadMemoryMiddleware(
            backend=_build_backend(workspace),
            sources=[memory_path],
        )
    ]


def _build_agent(user_id: str | None = None) -> CompiledStateGraph:
    """构建 Agent 实例（内部函数，供 channels 调用）。

    每个用户拥有独立的 workspace 目录：
        session/{user_id}/workspace/
            ├── memory/AGENTS.md   # 长期记忆
            ├── test2.txt          # 用户文件
            └── ...

    Agent 的文件操作被限制在用户 workspace 内，不同用户互相隔离。

    Args:
        user_id: 用户标识（如飞书 open_id），用于隔离用户工作空间。
                  为 None 时使用 "default" 目录。

    Returns:
        编译后的 Deep Agent 实例。
    """
    uid = user_id or "default"
    workspace = _get_user_workspace(uid)
    logger.info("用户工作空间: %s (user_id=%s)", workspace, uid)

    return create_deep_agent(
        model=create_llm(),
        tools=[internet_search],
        system_prompt=get_main_agent_prompt(),
        backend=_build_backend(workspace),
        checkpointer=_get_checkpointer(),
        interrupt_on={
            "edit_file": True,
            "execute": True,
        },
        middleware=_build_memory_middleware(workspace, uid),
    )


def create_main_agent() -> CompiledStateGraph:
    """创建主 Agent（LangGraph dev 工厂入口，无参数）。

    使用 "default" 用户目录，适用于 CLI 模式或 LangGraph dev 调试。

    Returns:
        编译后的 Deep Agent 实例。
    """
    return _build_agent(user_id=None)
