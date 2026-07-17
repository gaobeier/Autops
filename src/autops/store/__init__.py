"""Store 初始化 — 跨会话共享的持久化键值存储。

使用 PostgresStore（pgvector）实现，支持向量语义搜索。
复用 checkpointer 的 PostgreSQL 连接（需安装 pgvector 扩展）。

三种长期记忆类型：
- episodic：情景记忆（按用户隔离，存事件）
- semantic：语义记忆（全局共享，存知识）
- procedural：程序记忆（全局共享，存操作模式）
"""

from __future__ import annotations

import logging
from langchain_core.embeddings import Embeddings
from langgraph.store.base import BaseStore

from autops.config.settings import config

logger = logging.getLogger(__name__)

# 全局 store 单例
_store: BaseStore | None = None


class _OpenAICompatibleEmbeddings(Embeddings):
    """基于 OpenAI 兼容接口的 Embedding 封装。

    支持阿里 DashScope、OpenAI 等兼容 OpenAI API 的 embedding 服务。
    """

    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._model = model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        from openai import OpenAI
        client = OpenAI(api_key=self._api_key, base_url=self._base_url)
        resp = client.embeddings.create(model=self._model, input=texts)
        return [item.embedding for item in resp.data]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=self._api_key, base_url=self._base_url)
        resp = await client.embeddings.create(model=self._model, input=texts)
        return [item.embedding for item in resp.data]

    async def aembed_query(self, text: str) -> list[float]:
        result = await self.aembed_documents([text])
        return result[0]


def _create_embeddings() -> Embeddings:
    """创建 Embedding 实例。"""
    emb_cfg = config.store.embedding
    return _OpenAICompatibleEmbeddings(
        api_key=emb_cfg.api_key,
        base_url=emb_cfg.base_url,
        model=emb_cfg.model,
    )


def _get_store() -> BaseStore | None:
    """获取全局 store 单例。

    使用 PostgresStore（pgvector），复用 checkpointer 的 PG 连接。
    首次调用时初始化，需要 pgvector 扩展已安装。

    Returns:
        BaseStore 实例，未启用时返回 None。
    """
    global _store
    if _store is not None:
        return _store

    if not config.store.enabled:
        logger.info("Store 未启用，跳过初始化")
        return None

    from langgraph.store.postgres import PostgresStore
    from psycopg import Connection
    from psycopg.rows import dict_row

    pg = config.postgres
    conn_str = (
        f"host={pg.host} port={pg.port} user={pg.user} "
        f"password={pg.password} dbname={pg.database}"
    )
    emb_cfg = config.store.embedding

    conn = Connection.connect(
        conn_str,
        autocommit=True,
        prepare_threshold=0,
        row_factory=dict_row,
        options="-c search_path=public",
    )
    _store = PostgresStore(
        conn=conn,
        index={
            "dims": emb_cfg.dims,
            "fields": ["content", "trigger", "event"],
            "embed": _create_embeddings(),
        },
    )
    _store.setup()
    logger.info(
        "Store 已初始化 (PostgresStore: %s:%d/%s, model=%s, dims=%d)",
        pg.host, pg.port, pg.database, emb_cfg.model, emb_cfg.dims,
    )
    return _store


def get_store() -> BaseStore | None:
    """公开接口：获取 store 实例（用于 tools 模块）。"""
    return _get_store()
