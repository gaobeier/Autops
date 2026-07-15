"""每次都重新加载 AGENTS.md 的 MemoryMiddleware。

DeepAgents 官方的 MemoryMiddleware 出于 prompt cache 优化的考虑，
只在首次加载 AGENTS.md 内容到 state["memory_contents"]，
之后从 checkpointer 取 state 时会跳过读取。

这导致：
1. 用户手动修改 AGENTS.md → 不生效（checkpointer 缓存了旧内容）
2. Agent 通过 edit_file 修改 AGENTS.md → 不生效（state 不更新）

本中间件去掉"已加载则跳过"的判断，每次 invoke 都从磁盘重新读取 AGENTS.md。
代价：system prompt 内容会随 AGENTS.md 变化而变化（prompt cache 失效）。
对 qwen / OpenAI 等非 Anthropic 模型无影响（本来就没有 prompt cache）。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from deepagents.middleware.memory import (
    MemoryMiddleware,
    MemoryState,
    MemoryStateUpdate,
)

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig
    from langgraph.runtime import Runtime

logger = logging.getLogger(__name__)


class AlwaysReloadMemoryMiddleware(MemoryMiddleware):
    """每次 invoke 都重新从磁盘读取 AGENTS.md 的 MemoryMiddleware。

    与官方 MemoryMiddleware 的唯一区别：去掉 `if "memory_contents" in state: return None` 判断，
    每次 before_agent 都重新读文件，确保 AGENTS.md 的最新修改立即生效。
    """

    def before_agent(
        self, state: MemoryState, runtime: Runtime, config: RunnableConfig
    ) -> MemoryStateUpdate | None:
        """每次都重新从磁盘加载 AGENTS.md，覆盖 state 中的旧 memory_contents。"""
        backend = self._get_backend(state, runtime, config)
        contents: dict[str, str] = {}

        results = backend.download_files(list(self.sources))
        for path, response in zip(self.sources, results, strict=True):
            if response.error is not None:
                if response.error == "file_not_found":
                    continue
                msg = f"Failed to download {path}: {response.error}"
                raise ValueError(msg)
            if response.content is not None:
                contents[path] = response.content.decode("utf-8")
                logger.debug("Reloaded memory from: %s", path)

        logger.info(
            "AlwaysReloadMemory: 已加载 %d 个记忆文件, sources=%s",
            len(contents), self.sources,
        )
        return MemoryStateUpdate(memory_contents=contents)

    async def abefore_agent(
        self, state: MemoryState, runtime: Runtime, config: RunnableConfig
    ) -> MemoryStateUpdate | None:
        """异步版本：每次都重新从磁盘加载 AGENTS.md。"""
        backend = self._get_backend(state, runtime, config)
        contents: dict[str, str] = {}

        results = await backend.adownload_files(list(self.sources))
        for path, response in zip(self.sources, results, strict=True):
            if response.error is not None:
                if response.error == "file_not_found":
                    continue
                msg = f"Failed to download {path}: {response.error}"
                raise ValueError(msg)
            if response.content is not None:
                contents[path] = response.content.decode("utf-8")
                logger.debug("Reloaded memory from: %s", path)

        logger.info(
            "AlwaysReloadMemory: 已加载 %d 个记忆文件, sources=%s",
            len(contents), self.sources,
        )
        return MemoryStateUpdate(memory_contents=contents)
