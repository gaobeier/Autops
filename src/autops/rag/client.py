"""RAGFlow SDK 客户端 — 封装知识库检索接口。

仅用于知识库检索（retrieve），不涉及文档管理。
参考: https://ragflow.com.cn/docs/python_api_reference
"""

from __future__ import annotations

import logging
from typing import Any

from autops.config.settings import config

logger = logging.getLogger(__name__)

# 全局客户端单例
_client: RAGFlowClient | None = None


class RAGFlowClient:
    """RAGFlow SDK 客户端。

    封装 retrieve 接口，用于从知识库中检索相关文档片段。
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        dataset_ids: list[str] | None = None,
        similarity_threshold: float = 0.2,
        top_k: int = 5,
    ) -> None:
        from ragflow_sdk import RAGFlow

        self._rag = RAGFlow(api_key=api_key, base_url=base_url)
        self._dataset_ids = dataset_ids or []
        self._similarity_threshold = similarity_threshold
        self._top_k = top_k
        logger.info("RAGFlow SDK 客户端已创建: base_url=%s", base_url)

    def retrieve(
        self,
        question: str,
        dataset_ids: list[str] | None = None,
        top_k: int | None = None,
        similarity_threshold: float | None = None,
    ) -> list[dict[str, Any]]:
        """从知识库检索相关内容。

        Args:
            question: 检索问题（自然语言）。
            dataset_ids: 指定知识库 ID 列表，为空则使用配置中的默认值。
            top_k: 返回结果数量上限。
            similarity_threshold: 相似度阈值。

        Returns:
            检索结果列表，每项包含 content、similarity、document_name 等字段。
        """
        ids = dataset_ids or self._dataset_ids
        k = top_k or self._top_k
        threshold = similarity_threshold or self._similarity_threshold

        logger.info(
            "RAGFlow 检索: question=%r, dataset_ids=%s, top_k=%d",
            question[:100], ids or "(全部)", k,
        )

        chunks = self._rag.retrieve(
            dataset_ids=ids,
            question=question,
            page_size=k,
            similarity_threshold=threshold,
        )

        # 将 Chunk 对象转换为 dict
        results: list[dict[str, Any]] = []
        for chunk in chunks:
            results.append({
                "content": getattr(chunk, "content", ""),
                "similarity": getattr(chunk, "similarity", 0),
                "document_keyword": getattr(chunk, "document_keyword", ""),
                "document_name": getattr(chunk, "document_name", ""),
                "dataset_name": getattr(chunk, "dataset_name", ""),
                "document_id": getattr(chunk, "document_id", ""),
            })

        logger.info("RAGFlow 检索到 %d 个片段", len(results))
        return results


def get_ragflow_client() -> RAGFlowClient | None:
    """获取全局 RAGFlow 客户端单例。

    Returns:
        RAGFlowClient 实例，未启用时返回 None。
    """
    global _client
    if _client is not None:
        return _client

    ragflow_cfg = config.ragflow
    if not ragflow_cfg.enabled:
        logger.info("RAGFlow 未启用，跳过初始化")
        return None

    if not ragflow_cfg.api_key:
        logger.warning("RAGFlow api_key 未配置")
        return None

    _client = RAGFlowClient(
        api_key=ragflow_cfg.api_key,
        base_url=ragflow_cfg.base_url,
        dataset_ids=ragflow_cfg.dataset_ids,
        similarity_threshold=ragflow_cfg.similarity_threshold,
        top_k=ragflow_cfg.top_k,
    )
    logger.info(
        "RAGFlow 客户端已初始化: base_url=%s, dataset_ids=%s",
        ragflow_cfg.base_url, ragflow_cfg.dataset_ids or "(全部)",
    )
    return _client
