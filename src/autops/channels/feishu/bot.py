"""飞书 Bot — WebSocket 长连接模式，接收事件并分发到 Agent。

参考 Go 实现 example/bot.go 中的 FeishuBot（使用 larkws 长连接）。

使用 lark-oapi 官方 SDK 的 WebSocket 长连接：
1. 主动连接飞书服务器，无需公网 URL / Webhook
2. 收到消息后在线程中调用 Agent 处理
3. 通过 FeishuReporter 将回复发送回飞书

飞书开放平台需在「事件订阅」中选择「使用长连接接收事件」。
"""

from __future__ import annotations

import json
import logging
import re
import threading
from typing import Any

import time
from uuid import UUID

import lark_oapi as lark
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import HumanMessage
from lark_oapi.api.im.v1.model.p2_im_message_receive_v1 import P2ImMessageReceiveV1
from lark_oapi.event.dispatcher_handler import EventDispatcherHandler
from lark_oapi.ws.client import Client as WsClient

from autops.agents.main_agent import create_main_agent
from autops.channels.feishu.client import FeishuClient
from autops.channels.feishu.reporter import FeishuReporter
from autops.config.settings import config

logger = logging.getLogger(__name__)


def _truncate(text: Any, max_len: int = 500) -> str:
    """截断过长的文本用于日志展示。"""
    s = str(text)
    return s if len(s) <= max_len else s[:max_len] + "..."


class AgentObservabilityHandler(BaseCallbackHandler):
    """Agent 可观测性回调处理器。

    - 每次 LLM 调用递增 Turn 号
    - 工具调用时实时回调飞书通知
    - 调用结束后通过 summary() 返回精简统计
    """

    def __init__(self, reporter: FeishuReporter | None = None) -> None:
        self._timings: dict[UUID, float] = {}
        self._tool_names: dict[UUID, str] = {}
        self._reporter = reporter
        self._start_time = time.monotonic()
        self._model_name = config.llm.model
        self._turn = 0
        self._total_prompt_tokens = 0
        self._total_completion_tokens = 0
        self._tool_count = 0

    # ── LLM 相关 ────────────────────────────────────────────────

    def on_chat_model_start(
        self, serialized: dict, messages: list, *, run_id: UUID, **kwargs: Any
    ) -> None:
        kwargs_data = serialized.get("kwargs", {})
        model = kwargs_data.get("model_name") or kwargs_data.get("model") or self._model_name
        self._model_name = model
        self._timings[run_id] = time.monotonic()
        self._turn += 1
        msg_count = sum(len(m) for m in messages) if messages else 0
        logger.info("[Turn %d] 🧠 LLM 请求: model=%s, 消息数=%d", self._turn, model, msg_count)

    def on_llm_start(self, serialized: dict, prompts: list, *, run_id: UUID, **kwargs: Any) -> None:
        self._timings[run_id] = time.monotonic()

    def on_llm_end(self, response, *, run_id: UUID, **kwargs: Any) -> None:
        elapsed = self._get_elapsed(run_id)
        llm_output = getattr(response, "llm_output", None) or {}
        usage = llm_output.get("token_usage") or llm_output.get("usage") or {}
        prompt_t = usage.get("prompt_tokens", 0)
        completion_t = usage.get("completion_tokens", 0)
        total_t = usage.get("total_tokens", 0)
        self._total_prompt_tokens += prompt_t
        self._total_completion_tokens += completion_t
        token_info = f", tokens: {prompt_t}→{completion_t}(total={total_t})" if total_t else ""
        logger.info("[Turn %d] 🧠 LLM 响应: 耗时=%.1fs%s", self._turn, elapsed, token_info)

    def on_llm_error(self, error: Exception, *, run_id: UUID, **kwargs: Any) -> None:
        elapsed = self._get_elapsed(run_id)
        logger.error("[Turn %d] 🧠 LLM 错误: 耗时=%.1fs, error=%s", self._turn, elapsed, error)

    def on_llm_new_token(self, token: str, *, run_id: UUID, **kwargs: Any) -> None:
        pass

    # ── 工具相关 ────────────────────────────────────────────────

    def on_tool_start(
        self, serialized: dict, input_str: str, *, run_id: UUID, **kwargs: Any
    ) -> None:
        tool_name = serialized.get("name", "unknown")
        self._timings[run_id] = time.monotonic()
        self._tool_names[run_id] = tool_name
        self._tool_count += 1
        logger.info("[Turn %d] 🔧 调用工具: %s | 参数: %s", self._turn, tool_name, _truncate(input_str, 200))
        # 实时回调飞书
        if self._reporter:
            try:
                self._reporter.send_text(
                    f"🔧 [Turn {self._turn}] 调用工具: {tool_name}\n参数: {_truncate(input_str, 200)}"
                )
            except Exception:  # noqa: BLE001
                logger.exception("飞书工具调用通知发送失败")

    def on_tool_end(self, output: Any, *, run_id: UUID, **kwargs: Any) -> None:
        elapsed = self._get_elapsed(run_id)
        tool_name = self._tool_names.pop(run_id, "?")
        output_str = _truncate(output, 500)
        logger.info("[Turn %d] ✅ 工具结果: 耗时=%.1fs | %s", self._turn, elapsed, output_str)
        # 实时回调飞书
        if self._reporter:
            try:
                self._reporter.send_text(
                    f"✅ [Turn {self._turn}] {tool_name} 完成 ({elapsed:.1f}s)\n结果: {_truncate(output, 300)}"
                )
            except Exception:  # noqa: BLE001
                logger.exception("飞书工具结果通知发送失败")

    def on_tool_error(self, error: Exception, *, run_id: UUID, **kwargs: Any) -> None:
        elapsed = self._get_elapsed(run_id)
        tool_name = self._tool_names.pop(run_id, "?")
        logger.error("[Turn %d] ❌ 工具错误: 耗时=%.1fs | %s", self._turn, elapsed, error)
        if self._reporter:
            try:
                self._reporter.send_text(
                    f"❌ [Turn {self._turn}] {tool_name} 错误 ({elapsed:.1f}s): {error}"
                )
            except Exception:  # noqa: BLE001
                logger.exception("飞书工具错误通知发送失败")

    # ── Agent 决策 ──────────────────────────────────────────────

    def on_agent_action(self, action, *, run_id: UUID, **kwargs: Any) -> None:
        tool = getattr(action, "tool", "unknown")
        log = getattr(action, "log", "")
        logger.info("[Turn %d] 🤖 Agent 决策: 调用 %s | 思考: %s", self._turn, tool, _truncate(log, 200))

    def on_agent_finish(self, finish, *, run_id: UUID, **kwargs: Any) -> None:
        log = getattr(finish, "log", "")
        logger.info("[Turn %d] 🤖 Agent 完成: %s", self._turn, _truncate(log, 200) if log else "无日志")

    # ── 链路追踪 ────────────────────────────────────────────────

    def on_chain_start(
        self, serialized: dict | None, inputs: dict, *, run_id: UUID, **kwargs: Any
    ) -> None:
        self._timings[run_id] = time.monotonic()
        logger.debug("[Turn %d] ▶ 链路开始: %s", self._turn, (serialized or {}).get("name", "chain"))

    def on_chain_end(self, outputs: dict, *, run_id: UUID, **kwargs: Any) -> None:
        elapsed = self._get_elapsed(run_id)
        logger.debug("[Turn %d] ■ 链路结束: 耗时=%.1fs", self._turn, elapsed)

    def on_chain_error(self, error: Exception, *, run_id: UUID, **kwargs: Any) -> None:
        elapsed = self._get_elapsed(run_id)
        logger.error("[Turn %d] ■ 链路错误: 耗时=%.1fs | %s", self._turn, elapsed, error)

    # ── 重试 ────────────────────────────────────────────────────

    def on_retry(self, retry_state, *, run_id: UUID, **kwargs: Any) -> None:
        attempt = getattr(retry_state, "attempt_number", "?")
        logger.warning("[Turn %d] 🔄 重试: 第 %s 次", self._turn, attempt)

    # ── 辅助 ────────────────────────────────────────────────────

    def _get_elapsed(self, run_id: UUID) -> float:
        start = self._timings.pop(run_id, None)
        return time.monotonic() - start if start else 0.0

    def summary(self) -> str:
        """生成统计摘要。"""
        total_tokens = self._total_prompt_tokens + self._total_completion_tokens
        total_elapsed = time.monotonic() - self._start_time
        return (
            f"📊 执行统计\n"
            f"🔄 Turn: {self._turn}\n"
            f"🤖 模型: {self._model_name}\n"
            f"⏱️ 总耗时: {total_elapsed:.1f}s\n"
            f"📥 Token 输入: {self._total_prompt_tokens}\n"
            f"📤 Token 输出: {self._total_completion_tokens}\n"
            f"🎯 Token 合计: {total_tokens}"
        )


# ── 消息内容解析 ────────────────────────────────────────────────


def _parse_text_content(content_json: str) -> str:
    """解析飞书文本消息内容。

    飞书文本消息 Content 格式: {"text":"实际内容"}
    """
    try:
        data = json.loads(content_json)
        return data.get("text", "")
    except (json.JSONDecodeError, TypeError):
        return content_json


def _parse_image_key(content_json: str) -> str:
    """解析纯图片消息的 image_key。

    飞书图片消息 Content 格式: {"image_key":"img_xxx"}
    """
    try:
        data = json.loads(content_json)
        return data.get("image_key", "")
    except (json.JSONDecodeError, TypeError):
        return ""


def _parse_post_content(content_json: str) -> tuple[str, list[str]]:
    """解析飞书富文本消息，提取文本和图片。

    飞书 post 消息格式:
    {"title":"标题","content":[[{"tag":"text","text":".."}, {"tag":"img","image_key":"img_xxx"}]]}
    可能有多语言包裹: {"zh_cn":{"title":"...","content":[...]}}

    Returns:
        (文本内容, 图片 image_key 列表) 的元组。
    """
    try:
        post = json.loads(content_json)
    except (json.JSONDecodeError, TypeError):
        return "", []

    for lang_key in ("zh_cn", "en_us"):
        if lang_key in post and isinstance(post[lang_key], dict):
            post = post[lang_key]
            break

    parts: list[str] = []
    image_keys: list[str] = []
    title = post.get("title", "")
    if title:
        parts.append(title)

    for paragraph in post.get("content", []):
        for node in paragraph:
            tag = node.get("tag", "")
            if tag == "text" and node.get("text"):
                parts.append(node["text"])
            elif tag == "img" and node.get("image_key"):
                image_keys.append(node["image_key"])

    return "\n".join(parts), image_keys


def _strip_mention_text(text: str) -> str:
    """去除 @机器人 文本前缀（飞书消息中文本格式为 '@_user_1 你好'）。"""
    cleaned = re.sub(r"@_user_\d+\s*", "", text)
    return cleaned.strip()


def _is_mentioned(mentions: list | None, bot_open_id: str) -> bool:
    """检测群聊消息是否 @了机器人。"""
    if not bot_open_id:
        return True
    if not mentions:
        return False

    for m in mentions:
        if not m:
            continue
        m_id = getattr(m, "id", None)
        if m_id:
            open_id = getattr(m_id, "open_id", "") if not isinstance(m_id, str) else m_id
            if open_id == bot_open_id:
                return True
    return False


# ── 消息处理 ────────────────────────────────────────────────────


def _handle_message(
    client: FeishuClient,
    chat_id: str,
    message_id: str,
    content: str,
    user_id: str,
    image_data_urls: list[str] | None = None,
) -> None:
    """处理消息并调用 Agent（在独立线程中执行）。

    使用 LangGraph checkpointer 自动管理多轮对话状态，
    通过 thread_id（chat_id + user_id）区分不同会话。
    每次调用只需传入新的用户消息，checkpointer 自动加载历史。

    Args:
        client: FeishuClient 实例。
        chat_id: 会话 ID。
        message_id: 消息 ID（用于回复）。
        content: 消息文本内容。
        user_id: 发送者 ID。
        image_data_urls: 图片 data URL 列表（base64 编码），用于多模态消息。
    """
    thread_id = f"{chat_id}_{user_id}"

    # 构建用户消息（纯文本或多模态）
    if image_data_urls:
        content_parts: list[dict] = []
        if content.strip():
            content_parts.append({"type": "text", "text": content})
        else:
            content_parts.append({"type": "text", "text": "（用户发送了一张图片）"})
        for url in image_data_urls:
            content_parts.append({"type": "image_url", "image_url": {"url": url}})
        user_msg = HumanMessage(content=content_parts)
        logger.info("多模态消息: 文本=%d字符, 图片=%d张", len(content), len(image_data_urls))
    else:
        user_msg = HumanMessage(content=content)

    reporter = FeishuReporter(client, chat_id, message_id)

    try:
        reporter.send_text("💭 思考中...")
    except Exception:  # noqa: BLE001
        logger.exception("发送思考中提示失败")

    try:
        handler = AgentObservabilityHandler(reporter=reporter)
        agent = create_main_agent()
        result = agent.invoke(
            {"messages": [user_msg]},
            config={
                "thread_id": thread_id,
                "recursion_limit": config.agent.recursion_limit,
                "callbacks": [handler],
            },
        )
        logger.info("Agent 调用完成 (Turn %d)", handler._turn)

        ai_messages = result.get("messages", [])
        if ai_messages:
            last = ai_messages[-1]
            reply = last.content if hasattr(last, "content") else str(last)
            reply_str = str(reply)
            logger.info("回复长度: %d 字符", len(reply_str))
            reporter.send_text(reply_str)
            # 发送执行统计
            reporter.send_text(handler.summary())
        else:
            logger.warning("Agent 返回空消息列表")
            reporter.send_text("⚠️ 未收到回复")
    except Exception as e:  # noqa: BLE001
        logger.exception("Agent 处理出错")
        try:
            reporter.send_text(f"❌ 处理出错: {e}")
        except Exception:  # noqa: BLE001
            logger.exception("发送错误消息也失败了")


# ── 事件处理 ────────────────────────────────────────────────────


def _on_message_receive(client: FeishuClient, event: P2ImMessageReceiveV1) -> None:
    """处理飞书消息接收事件。

    Args:
        client: FeishuClient 实例（用于发送回复）。
        event: 飞书 P2ImMessageReceiveV1 事件对象。
    """
    try:
        msg = event.event.message
        sender = event.event.sender
    except AttributeError:
        logger.error("事件缺少 event/message/sender 字段: %s", event)
        return

    message_id = msg.message_id or ""
    chat_id = msg.chat_id or ""
    chat_type = msg.chat_type or ""
    msg_type = msg.message_type or ""
    raw_content = msg.content or ""
    mentions = msg.mentions

    sender_id = ""
    if sender and sender.sender_id:
        sender_id = sender.sender_id.open_id or ""

    logger.info(
        "收到消息: chat_id=%s, chat_type=%s, msg_type=%s, user=%s, msg_id=%s",
        chat_id, chat_type, msg_type, sender_id, message_id,
    )
    logger.debug("消息原始 content: %s", raw_content[:500])

    # 群聊场景：只在被 @提及时响应
    if chat_type == "group":
        try:
            bot_open_id = client.get_bot_open_id()
        except Exception:  # noqa: BLE001
            logger.exception("获取 Bot OpenID 失败")
            bot_open_id = ""

        if not _is_mentioned(mentions, bot_open_id):
            logger.info("群聊消息未 @机器人，忽略: chat_id=%s", chat_id)
            return
        logger.info("群聊消息已 @机器人，开始处理")

    # 解析消息内容
    content = ""
    image_keys: list[str] = []

    if msg_type == "text":
        content = _parse_text_content(raw_content)
        if chat_type == "group":
            content = _strip_mention_text(content)
    elif msg_type == "post":
        content, image_keys = _parse_post_content(raw_content)
    elif msg_type == "image":
        image_key = _parse_image_key(raw_content)
        if image_key:
            image_keys = [image_key]
        else:
            logger.warning("图片消息缺少 image_key")
            return
    else:
        logger.info("忽略不支持的消息类型: %s", msg_type)
        return

    logger.info("解析后的消息内容: %s, 图片数: %d",
                content[:200] if content else "(空)", len(image_keys))

    if not content.strip() and not image_keys:
        logger.warning("消息内容为空且无图片，跳过")
        return

    # 下载图片并转换为 base64 data URL
    image_data_urls: list[str] = []
    for img_key in image_keys:
        try:
            data_url = client.download_image_as_base64(message_id, img_key)
            image_data_urls.append(data_url)
        except Exception:  # noqa: BLE001
            logger.exception("下载图片失败: image_key=%s", img_key)

    # 在新线程中处理（避免阻塞事件循环）
    thread = threading.Thread(
        target=_handle_message,
        args=(client, chat_id, message_id, content, sender_id, image_data_urls),
        daemon=True,
    )
    thread.start()
    logger.info("已启动处理线程: msg_id=%s", message_id)


# ── 日志配置 ────────────────────────────────────────────────────


def _setup_logging() -> None:
    """配置 autops 和 lark SDK 命名空间的日志。

    日志级别从 config.yaml 的 log_level 字段读取（默认 INFO）。
    不使用 force=True，避免覆盖 LangChain / Deepagents 等库的日志配置。
    仅配置 autops.* 命名空间的 logger，设置 propagate=False 防止
    日志向上传播到 root logger 造成重复输出。
    """
    level = config.logging_level

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # autops 命名空间
    autops_logger = logging.getLogger("autops")
    autops_logger.setLevel(level)
    autops_logger.propagate = False
    if not autops_logger.handlers:
        h = logging.StreamHandler()
        h.setLevel(level)
        h.setFormatter(fmt)
        autops_logger.addHandler(h)
    else:
        for h in autops_logger.handlers:
            h.setLevel(level)

    # lark SDK 命名空间（SDK 内部 logger 名为 "Lark"）
    lark_logger = logging.getLogger("Lark")
    lark_logger.setLevel(level)
    for h in lark_logger.handlers:
        h.setLevel(level)
        h.setFormatter(fmt)

    # 降低其他第三方库日志级别
    for name in ("httpx", "httpcore", "openai", "urllib3"):
        logging.getLogger(name).setLevel(logging.WARNING)


# ── 启动入口 ────────────────────────────────────────────────────


def run_feishu() -> None:
    """启动飞书 WebSocket 长连接。"""
    _setup_logging()

    feishu_cfg = config.feishu

    if not feishu_cfg.app_id or not feishu_cfg.app_secret:
        logger.error("未配置飞书 app_id / app_secret")
        return

    # 创建 FeishuClient（用于发送消息）
    client = FeishuClient(feishu_cfg.app_id, feishu_cfg.app_secret)

    # 获取 Bot OpenID
    try:
        bot_open_id = client.get_bot_open_id()
        logger.info("Bot OpenID: %s", bot_open_id)
    except Exception as e:  # noqa: BLE001
        logger.warning("获取 Bot OpenID 失败: %s", e)

    # 构建事件处理器
    event_handler = (
        EventDispatcherHandler.builder("", "")
        .register_p2_im_message_receive_v1(
            lambda event: _on_message_receive(client, event)
        )
        .build()
    )

    # 创建 WebSocket 长连接客户端
    ws_client = WsClient(
        app_id=feishu_cfg.app_id,
        app_secret=feishu_cfg.app_secret,
        event_handler=event_handler,
        log_level=lark.LogLevel(config.logging_level),
    )

    logger.info("═══════════════════════════════════════")
    logger.info("  Autops 飞书通道已启动")
    logger.info("  模式: WebSocket 长连接")
    logger.info("  模型: %s", config.llm.model)
    logger.info("  日志级别: %s", config.log_level.upper())
    logger.info("  按 Ctrl+C 退出")
    logger.info("═══════════════════════════════════════")

    # 启动长连接（阻塞）
    try:
        ws_client.start()
    except KeyboardInterrupt:
        logger.info("飞书通道已停止")
    except Exception as e:  # noqa: BLE001
        logger.exception("飞书通道异常退出: %s", e)
