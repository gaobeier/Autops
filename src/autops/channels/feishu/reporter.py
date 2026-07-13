"""飞书消息报告器 — 向飞书发送消息的统一出口。

参考 Go 实现 example/reporter.go 中的 FeishuReporter。
"""

from __future__ import annotations

import json

from autops.channels.feishu.client import FeishuClient


class FeishuReporter:
    """飞书消息报告器，封装回复消息的逻辑。

    优先回复原始消息（reply），无 message_id 时发送到会话（create）。
    日志由 FeishuClient 统一记录，此处不再重复打印。

    Args:
        client: FeishuClient 实例。
        chat_id: 会话 ID。
        message_id: 被回复的消息 ID（可选）。
    """

    def __init__(self, client: FeishuClient, chat_id: str, message_id: str = "") -> None:
        self.client = client
        self.chat_id = chat_id
        self.message_id = message_id

    def send_text(self, text: str) -> None:
        """发送文本消息。

        Args:
            text: 文本内容。
        """
        self.client.send_text(self.chat_id, text, reply_to=self.message_id)

    def send_card(self, card: dict) -> dict:
        """发送交互式卡片消息（reply 到原用户消息）。

        审批卡片 reply 到原用户消息，与上下文关联更清晰。

        Args:
            card: 卡片内容字典。

        Returns:
            飞书 API 响应字典（含 message_id）。
        """
        return self.client.send_card(self.chat_id, card, reply_to=self.message_id)

    def update_card(self, message_id: str, card: dict) -> dict:
        """更新已发送的卡片内容。

        Args:
            message_id: 已发送卡片消息的 ID。
            card: 新的卡片内容字典。

        Returns:
            飞书 API 响应字典。
        """
        return self.client.patch_message(message_id, json.dumps(card))
