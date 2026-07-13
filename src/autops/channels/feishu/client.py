"""飞书 API 客户端 — 封装 token 管理和消息发送。

参考 Go 实现 example/bot.go 中的 getTenantAccessToken / SendText / SendCard。
"""

from __future__ import annotations

import base64
import json
import logging
import os
import threading
import time

import httpx

logger = logging.getLogger(__name__)

_FEISHU_BASE = "https://open.feishu.cn/open-apis"


class FeishuClient:
    """飞书 API 客户端，管理 tenant_access_token 并提供消息发送接口。

    Args:
        app_id: 飞书应用 App ID。
        app_secret: 飞书应用 App Secret。
    """

    def __init__(self, app_id: str, app_secret: str) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self._token: str = ""
        self._token_expiry: float = 0.0
        self._lock = threading.Lock()
        self._bot_open_id: str = ""

    # ── Token 管理 ──────────────────────────────────────────────

    def get_tenant_access_token(self) -> str:
        """获取 tenant_access_token（带缓存，提前 5 分钟刷新）。

        Returns:
            有效的 tenant_access_token 字符串。
        """
        with self._lock:
            if self._token and time.time() < self._token_expiry - 300:
                return self._token

            resp = httpx.post(
                f"{_FEISHU_BASE}/auth/v3/tenant_access_token/internal",
                json={"app_id": self.app_id, "app_secret": self.app_secret},
                timeout=10,
            )
            data = resp.json()
            token = data.get("tenant_access_token", "")
            if not token:
                raise RuntimeError(
                    f"获取 tenant_access_token 失败: code={data.get('code')}, msg={data.get('msg')}"
                )

            expire = data.get("expire", 7200)
            self._token = token
            self._token_expiry = time.time() + expire
            logger.info("tenant_access_token 已刷新，有效期 %ds", expire)
            return token

    def _headers(self) -> dict[str, str]:
        """构造带 Authorization 的请求头。"""
        return {"Authorization": f"Bearer {self.get_tenant_access_token()}"}

    # ── Bot 信息 ────────────────────────────────────────────────

    def get_bot_open_id(self) -> str:
        """获取机器人自身的 OpenID（懒加载 + 缓存）。

        用于群聊场景下检测是否被 @提及。

        Returns:
            Bot 的 OpenID 字符串。
        """
        if self._bot_open_id:
            return self._bot_open_id

        resp = httpx.get(
            f"{_FEISHU_BASE}/bot/v3/info",
            headers=self._headers(),
            timeout=10,
        )
        data = resp.json()
        bot = data.get("bot", {})
        self._bot_open_id = bot.get("open_id", "")
        logger.info("Bot OpenID: %s", self._bot_open_id)
        return self._bot_open_id

    # ── 消息发送 ────────────────────────────────────────────────

    def send_message(self, chat_id: str, content: str, msg_type: str = "text") -> dict:
        """发送消息到指定会话。

        Args:
            chat_id: 会话 ID。
            content: 消息内容 JSON 字符串。
            msg_type: 消息类型（text / interactive 等）。

        Returns:
            飞书 API 响应字典。
        """
        resp = httpx.post(
            f"{_FEISHU_BASE}/im/v1/messages",
            params={"receive_id_type": "chat_id"},
            headers=self._headers(),
            json={
                "receive_id": chat_id,
                "content": content,
                "msg_type": msg_type,
            },
            timeout=10,
        )
        result = resp.json()
        logger.debug("发送消息: chat_id=%s, msg_type=%s, code=%s",
                     chat_id, msg_type, result.get("code"))
        return result

    def reply_message(self, message_id: str, content: str, msg_type: str = "text") -> dict:
        """回复指定消息。

        Args:
            message_id: 被回复的消息 ID。
            content: 消息内容 JSON 字符串。
            msg_type: 消息类型（text / interactive 等）。

        Returns:
            飞书 API 响应字典。
        """
        resp = httpx.post(
            f"{_FEISHU_BASE}/im/v1/messages/{message_id}/reply",
            headers=self._headers(),
            json={"content": content, "msg_type": msg_type},
            timeout=10,
        )
        result = resp.json()
        logger.debug("回复消息: msg_id=%s, msg_type=%s, code=%s",
                     message_id, msg_type, result.get("code"))
        return result

    def patch_message(self, message_id: str, content: str) -> dict:
        """更新已发送消息的内容（仅支持 interactive 卡片）。

        API: PATCH /open-apis/im/v1/messages/{message_id}

        Args:
            message_id: 已发送消息的 ID。
            content: 新的卡片内容 JSON 字符串。

        Returns:
            飞书 API 响应字典。
        """
        resp = httpx.patch(
            f"{_FEISHU_BASE}/im/v1/messages/{message_id}",
            headers=self._headers(),
            json={"content": content},
            timeout=10,
        )
        result = resp.json()
        logger.debug("更新消息: msg_id=%s, code=%s", message_id, result.get("code"))
        return result

    # ── 资源下载 ────────────────────────────────────────────────

    def download_image(self, message_id: str, file_key: str) -> tuple[bytes, str]:
        """下载用户发送的图片。

        使用"获取消息中的资源文件"接口（非 images/{image_key} 接口）。
        API: GET /open-apis/im/v1/messages/{message_id}/resources/{file_key}?type=image

        Args:
            message_id: 图片所在消息的 ID。
            file_key: 图片的 file_key（即 image_key）。

        Returns:
            (图片二进制数据, MIME 类型) 的元组。

        Raises:
            RuntimeError: 下载失败时抛出。
        """
        resp = httpx.get(
            f"{_FEISHU_BASE}/im/v1/messages/{message_id}/resources/{file_key}",
            params={"type": "image"},
            headers=self._headers(),
            timeout=30,
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"下载图片失败: status={resp.status_code}, file_key={file_key}"
            )

        # 从 Content-Disposition 推断文件扩展名，映射到 MIME 类型
        mime_type = "image/jpeg"  # 飞书图片默认 jpeg
        cd = resp.headers.get("Content-Disposition", "")
        if cd:
            for part in cd.split(";"):
                part = part.strip()
                if part.startswith("filename="):
                    filename = part.split("=", 1)[1].strip('"')
                    ext = os.path.splitext(filename)[1].lower()
                    mime_map = {
                        ".png": "image/png",
                        ".gif": "image/gif",
                        ".webp": "image/webp",
                        ".bmp": "image/bmp",
                    }
                    mime_type = mime_map.get(ext, mime_type)
                    break

        img_bytes = resp.content
        logger.info("图片下载成功: file_key=%s, size=%d bytes, type=%s",
                     file_key, len(img_bytes), mime_type)
        return img_bytes, mime_type

    def download_image_as_base64(self, message_id: str, file_key: str) -> str:
        """下载图片并返回 data URL（base64 编码）。

        Args:
            message_id: 图片所在消息的 ID。
            file_key: 图片的 file_key。

        Returns:
            data URL 字符串，如 "data:image/jpeg;base64,/9j/4AAQ..."
        """
        img_bytes, mime_type = self.download_image(message_id, file_key)
        b64 = base64.b64encode(img_bytes).decode("utf-8")
        return f"data:{mime_type};base64,{b64}"

    # ── 便捷方法 ────────────────────────────────────────────────

    def send_text(self, chat_id: str, text: str, reply_to: str = "") -> dict:
        """发送文本消息。

        Args:
            chat_id: 会话 ID。
            text: 文本内容。
            reply_to: 若提供，则回复该消息 ID。

        Returns:
            飞书 API 响应字典。
        """
        content = json.dumps({"text": text})
        if reply_to:
            return self.reply_message(reply_to, content, "text")
        return self.send_message(chat_id, content, "text")

    def send_card(self, chat_id: str, card: dict, reply_to: str = "") -> dict:
        """发送交互式卡片消息。

        Args:
            chat_id: 会话 ID。
            card: 卡片内容字典。
            reply_to: 若提供，则回复该消息 ID。

        Returns:
            飞书 API 响应字典。
        """
        content = json.dumps(card)
        if reply_to:
            return self.reply_message(reply_to, content, "interactive")
        return self.send_message(chat_id, content, "interactive")
