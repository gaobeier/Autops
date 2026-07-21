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
from autops.middleware import AlwaysReloadMemoryMiddleware, CommandSafetyMiddleware
from autops.prompts.system import get_main_agent_prompt
from autops.store import get_store
from autops.store.episodic import _make_episodic_tools
from autops.store.procedural import _make_procedural_tools
from autops.store.semantic import _make_semantic_tools
from autops.rag.tools import search_rag_knowledge
from autops.tools import internet_search, should_interrupt_execute

logger = logging.getLogger(__name__)

# 全局 checkpointer 单例（所有会话共享，通过 thread_id 区分）
_checkpointer: PostgresSaver | None = None

# 会话根目录（所有用户的 session 数据存放于此）
# 模块级别预创建（在 LangGraph dev 的线程池中执行，允许阻塞 I/O）
_SESSION_ROOT = Path(config.agent.workspace).resolve() / "session"
_SESSION_ROOT.mkdir(parents=True, exist_ok=True)

# 预创建 default 用户工作空间（LangGraph dev / CLI 用）
_DEFAULT_WORKSPACE = _SESSION_ROOT / "default" / "workspace"
_DEFAULT_WORKSPACE.mkdir(parents=True, exist_ok=True)
# 预创建 default 的 memory 目录
(_DEFAULT_WORKSPACE / "memory").mkdir(parents=True, exist_ok=True)
logger.info("会话根目录: %s", _SESSION_ROOT)


def _get_user_workspace(user_id: str) -> Path:
    """获取用户工作空间路径（不做 I/O）。

    目录结构: session/{user_id}/workspace/
    目录由调用方在非事件循环线程中创建（飞书 channel 的处理线程）。
    LangGraph dev 只用 default workspace（模块级别已预创建）。

    Args:
        user_id: 用户标识（如飞书 open_id）。

    Returns:
        用户工作空间目录路径（可能尚未创建）。
    """
    if user_id == "default":
        return _DEFAULT_WORKSPACE
    ws = _SESSION_ROOT / user_id / "workspace"
    # 飞书 channel 在独立线程中调用，可以阻塞
    # LangGraph dev 只走 default 分支，不会到这里
    if not ws.exists():
        ws.mkdir(parents=True, exist_ok=True)
        # 同时创建 memory 子目录
        (ws / "memory").mkdir(parents=True, exist_ok=True)
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

    注意：本函数不做 mkdir（避免事件循环中的阻塞 I/O）。
    memory 目录由飞书 channel 的处理线程创建，或由 Agent 的 write_file 工具自动创建。

    Args:
        workspace: 用户工作空间路径。
        user_id: 用户标识（仅用于日志）。

    Returns:
        中间件列表（可能为空）。
    """
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

    # 安全策略（三级）：
    # 1. 高危（硬编码）：CommandSafetyMiddleware 拦截，直接拒绝
    # 2. 危险（config.yaml 可配）：should_interrupt_execute 谓词，触发人工审批
    # 3. 低风险（默认）：直接放行
    from langchain.agents.middleware import InterruptOnConfig

    # 中间件列表：安全拦截 + 长期记忆
    middleware = [
        CommandSafetyMiddleware(),
        *_build_memory_middleware(workspace, uid),
    ]

    # 工具列表
    tools = [internet_search]

    # RAGFlow 知识库检索工具
    from autops.config.settings import config as _cfg
    if _cfg.ragflow.enabled:
        tools.append(search_rag_knowledge)
        logger.info("已加载 RAGFlow 知识库检索工具: search_rag_knowledge")

    # Store（长期记忆：情景/语义/程序）
    store = get_store()
    if store is not None:
        tools.extend(_make_episodic_tools(uid))   # 情景记忆（按用户隔离）
        tools.extend(_make_semantic_tools())       # 语义记忆（全局共享）
        tools.extend(_make_procedural_tools())     # 程序记忆（全局共享）
        logger.info("已加载 Store 工具: episodic + semantic + procedural")

    return create_deep_agent(
        model=create_llm(),
        tools=tools,
        system_prompt=get_main_agent_prompt(),
        backend=_build_backend(workspace),
        checkpointer=_get_checkpointer(),
        store=store,
        interrupt_on={
            "edit_file": True,
            "execute": InterruptOnConfig(
                allowed_decisions=["approve", "reject"],
                when=should_interrupt_execute,
            ),
        },
        middleware=middleware,
    )


def create_main_agent() -> CompiledStateGraph:
    """创建主 Agent（LangGraph dev 工厂入口，无参数）。

    使用 "default" 用户目录，适用于 CLI 模式或 LangGraph dev 调试。

    Returns:
        编译后的 Deep Agent 实例。
    """
    return _build_agent(user_id=None)
