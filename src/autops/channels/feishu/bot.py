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

import time

import lark_oapi as lark
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from lark_oapi.api.im.v1.model.p2_im_message_receive_v1 import P2ImMessageReceiveV1
from lark_oapi.event.callback.model.p2_card_action_trigger import (
    P2CardActionTrigger,
)
from lark_oapi.event.dispatcher_handler import EventDispatcherHandler
from lark_oapi.ws.client import Client as WsClient

from autops.agents.main_agent import _build_agent
from autops.channels.feishu.client import FeishuClient
from autops.channels.feishu.reporter import FeishuReporter
from autops.config.settings import config
from autops.observability import AgentObservabilityHandler

logger = logging.getLogger(__name__)


# ── 审批卡片会话注册表 ──────────────────────────────────────────
# thread_id → (reporter, card_message_id, user_id)，用于卡片回调后更新卡片并继续发送消息。
_pending_approvals: dict[str, tuple[FeishuReporter, str, str]] = {}
_pending_lock = threading.Lock()


class FeishuEventSink:
    """飞书事件输出适配器 — 实现 EventSink 协议。

    将通用可观测性事件转换为飞书消息发送。
    """

    def __init__(self, reporter: FeishuReporter) -> None:
        self._reporter = reporter

    def notify_tool_start(self, turn: int, tool_name: str, params: str) -> None:
        self._reporter.send_text(
            f"🔧 [Turn {turn}] 调用工具: {tool_name}\n参数: {params}"
        )

    def notify_tool_end(self, turn: int, tool_name: str, output: str, elapsed: float) -> None:
        self._reporter.send_text(
            f"✅ [Turn {turn}] {tool_name} 完成 ({elapsed:.1f}s)\n结果: {output}"
        )

    def notify_tool_error(self, turn: int, tool_name: str, error: str, elapsed: float) -> None:
        self._reporter.send_text(
            f"❌ [Turn {turn}] {tool_name} 错误 ({elapsed:.1f}s): {error}"
        )

    def notify_summary(self, summary: str) -> None:
        self._reporter.send_text(summary)


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


# ── 审批卡片 ────────────────────────────────────────────────────


def _build_approval_card(
    thread_id: str,
    action_requests: list[dict],
) -> dict:
    """构建人工审批飞书卡片。

    Args:
        thread_id: LangGraph 会话 ID（用于恢复 interrupt）。
        action_requests: interrupt 中的 action_requests 列表。

    Returns:
        飞书 interactive 卡片内容字典。
    """
    # 截断 args 以避免按钮 value 超过 5KB 限制
    safe_action_requests: list[dict] = []
    for req in action_requests:
        tool_name = req.get("name", "unknown")
        args = req.get("args", {})
        # 截断过大的 args（如长命令、长文件内容）
        safe_args: dict = {}
        for k, v in args.items():
            v_str = str(v)
            if len(v_str) > 500:
                safe_args[k] = v_str[:500] + "..."
            else:
                safe_args[k] = v
        safe_action_requests.append({"name": tool_name, "args": safe_args})

    # 构建工具调用描述（用于卡片正文展示）
    items: list[dict] = []
    for req in action_requests:
        tool_name = req.get("name", "unknown")
        args = req.get("args", {})
        args_str = json.dumps(args, ensure_ascii=False, indent=2)
        if len(args_str) > 800:
            args_str = args_str[:800] + "..."
        items.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**🔧 工具: `{tool_name}`**\n```\n{args_str}\n```",
            },
        })

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "⚠️ 人工审批请求"},
            "template": "orange",
        },
        "elements": [
            *items,
            {"tag": "hr"},
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "✅ 批准"},
                        "type": "primary",
                        "value": {
                            "thread_id": thread_id,
                            "decision": "approve",
                            # 保存 action_requests 用于回调后构建 done 卡片
                            "action_requests": safe_action_requests,
                        },
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "❌ 拒绝"},
                        "type": "danger",
                        "value": {
                            "thread_id": thread_id,
                            "decision": "reject",
                            "action_requests": safe_action_requests,
                        },
                    },
                ],
            },
        ],
    }


def _build_done_card(
    action_requests: list[dict],
    decision_type: str,
) -> dict:
    """构建已处理状态的卡片（更新原卡片，移除按钮防止重复点击）。

    Args:
        action_requests: interrupt 中的 action_requests 列表（用于展示内容）。
        decision_type: "approve" 或 "reject"。

    Returns:
        更新后的飞书 interactive 卡片内容字典。
    """
    items: list[dict] = []
    for req in action_requests:
        tool_name = req.get("name", "unknown")
        args = req.get("args", {})
        args_str = json.dumps(args, ensure_ascii=False, indent=2)
        if len(args_str) > 800:
            args_str = args_str[:800] + "..."
        items.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**🔧 工具: `{tool_name}`**\n```\n{args_str}\n```",
            },
        })

    if decision_type == "approve":
        status_text = "✅ 已批准"
        template = "green"
    else:
        status_text = "❌ 已拒绝"
        template = "red"

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"人工审批 · {status_text}"},
            "template": template,
        },
        "elements": [
            *items,
            {"tag": "hr"},
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"**{status_text}** — 已处理，无需重复点击。"},
            },
        ],
    }


def _on_card_action(event: P2CardActionTrigger) -> dict:
    """处理飞书卡片按钮回调。

    关键约束：飞书长连接模式下，回调函数必须在 **3 秒内** 返回，
    否则客户端会显示"目标回调服务超时未响应"。
    Agent 执行是耗时操作，必须放到后台线程异步执行。

    参考: https://open.feishu.cn/document/server-side-sdk/python--sdk/handle-callbacks

    Args:
        event: 飞书卡片回调事件。

    Returns:
        dict 响应（含 toast 和/或 card），3 秒内返回。
    """
    try:
        action = event.event.action
        if not action or not action.value:
            logger.warning("卡片回调缺少 action.value")
            return {"toast": {"type": "error", "content": "回调数据无效"}}

        value = action.value
        thread_id = value.get("thread_id", "")
        decision_type = value.get("decision", "")

        if not thread_id or not decision_type:
            logger.warning("卡片回调缺少 thread_id 或 decision: %s", value)
            return {"toast": {"type": "error", "content": "回调数据无效"}}

        logger.info("收到卡片审批: thread_id=%s, decision=%s", thread_id, decision_type)

        # 取出 reporter 和卡片 message_id
        with _pending_lock:
            entry = _pending_approvals.pop(thread_id, None)

        if entry is None:
            # 已处理或重复点击的回调，属于正常情况
            logger.info("卡片回调无对应会话（已处理或重复点击）: thread_id=%s", thread_id)
            return {"toast": {"type": "info", "content": "已处理，无需重复操作"}}

        reporter, card_message_id, user_id = entry

        # 构造 decision
        if decision_type == "approve":
            decision = {"type": "approve"}
            toast = {"type": "success", "content": "已批准，继续执行"}
        elif decision_type == "reject":
            decision = {"type": "reject", "message": "用户拒绝了此操作"}
            toast = {"type": "info", "content": "已拒绝"}
        else:
            logger.warning("未知的 decision 类型: %s", decision_type)
            return {"toast": {"type": "error", "content": "未知操作"}}

        # 构建已处理状态的卡片
        done_card = _build_done_card(
            value.get("action_requests", [{"name": "?", "args": {}}]),
            decision_type,
        )

        # 从事件 context 取卡片消息 ID（参考 Go 实现 bot.go:193-195）
        card_msg_id = ""
        if event.event and event.event.context:
            card_msg_id = event.event.context.open_message_id or ""
        if not card_msg_id:
            card_msg_id = card_message_id  # 回退到发送时保存的

        # 立即返回 toast 响应（必须在 3 秒内）
        # 卡片更新和 Agent 执行放到后台线程，避免阻塞回调
        def _background() -> None:
            # 1) PATCH 更新卡片
            if card_msg_id:
                try:
                    time.sleep(0.5)  # 延迟确保回调响应已返回
                    result = reporter.update_card(card_msg_id, done_card)
                    code = result.get("code", -1) if isinstance(result, dict) else -1
                    if code == 0:
                        logger.info("卡片更新成功: msg_id=%s", card_msg_id)
                    else:
                        logger.warning(
                            "卡片更新失败: msg_id=%s, code=%s, response=%s",
                            card_msg_id, code, result,
                        )
                except Exception:  # noqa: BLE001
                    logger.exception("异步更新卡片失败")

            # 2) 恢复 Agent 执行
            try:
                resume_handler = AgentObservabilityHandler(sink=FeishuEventSink(reporter))
                agent = _build_agent(user_id=user_id or None)
                result = agent.invoke(
                    Command(resume={"decisions": [decision]}),
                    config={
                        "thread_id": thread_id,
                        "recursion_limit": config.agent.recursion_limit,
                        "callbacks": [resume_handler],
                    },
                )

                ai_messages = result.get("messages", [])
                if ai_messages:
                    last = ai_messages[-1]
                    reply = last.content if hasattr(last, "content") else str(last)
                    reply_str = str(reply)
                    if reply_str.strip():
                        logger.info("审批后回复长度: %d 字符", len(reply_str))
                        reporter.send_text(reply_str)

                # 检查是否还有新的 interrupt（连续多个危险操作）
                interrupts = result.get("__interrupt__", [])
                if interrupts:
                    _handle_interrupts(interrupts, thread_id, reporter, user_id=user_id)
                else:
                    # 正常完成，发送执行统计（summary 内部会通过 sink 发送到飞书）
                    resume_handler.summary()
            except Exception:  # noqa: BLE001
                logger.exception("后台 Agent 执行出错")

        threading.Thread(target=_background, daemon=True).start()

        # 立即返回响应（3 秒内）
        return {"toast": toast}

    except Exception:  # noqa: BLE001
        logger.exception("卡片回调处理出错")
        return {"toast": {"type": "error", "content": "处理出错"}}


def _handle_interrupts(
    interrupts: list,
    thread_id: str,
    reporter: FeishuReporter,
    user_id: str = "",
) -> bool:
    """处理 Agent 返回的 interrupt，发送审批卡片。

    Args:
        interrupts: Agent 返回的 interrupt 列表。
        thread_id: LangGraph 会话 ID。
        reporter: 飞书消息报告器。
        user_id: 用户标识（用于审批后恢复时加载对应用户的长期记忆）。

    Returns:
        True 表示有 interrupt 需要处理（已发送卡片），False 表示无。
    """
    if not interrupts:
        return False

    # 取第一个 interrupt（通常只有一个）
    interrupt = interrupts[0]
    # Interrupt 对象有 value 和 id 属性
    interrupt_value = getattr(interrupt, "value", interrupt)
    if isinstance(interrupt_value, dict):
        action_requests = interrupt_value.get("action_requests", [])
    else:
        action_requests = []

    if not action_requests:
        logger.warning("interrupt 中无 action_requests: %s", interrupt_value)
        return False

    # 发送审批卡片，获取卡片消息 ID
    card = _build_approval_card(thread_id, action_requests)
    send_result = reporter.send_card(card)
    card_message_id = ""
    try:
        card_message_id = send_result.get("data", {}).get("message_id", "")
    except (AttributeError, TypeError):
        pass

    # 注册等待审批：thread_id → (reporter, card_message_id, user_id)
    with _pending_lock:
        _pending_approvals[thread_id] = (reporter, card_message_id, user_id)

    logger.info("已发送审批卡片: thread_id=%s, card_msg_id=%s", thread_id, card_message_id)
    return True


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
        handler = AgentObservabilityHandler(sink=FeishuEventSink(reporter))
        agent = _build_agent(user_id=user_id)
        result = agent.invoke(
            {"messages": [user_msg]},
            config={
                "thread_id": thread_id,
                "recursion_limit": config.agent.recursion_limit,
                "callbacks": [handler],
            },
        )
        logger.info("Agent 调用完成 (Turn %d)", handler._turn)

        # 检查是否触发 interrupt（人工审批）
        interrupts = result.get("__interrupt__", [])
        if interrupts:
            if _handle_interrupts(interrupts, thread_id, reporter, user_id=user_id):
                # 已发送审批卡片，等待用户在飞书中点击按钮
                return

        ai_messages = result.get("messages", [])
        if ai_messages:
            last = ai_messages[-1]
            reply = last.content if hasattr(last, "content") else str(last)
            reply_str = str(reply)
            logger.info("回复长度: %d 字符", len(reply_str))
            reporter.send_text(reply_str)
            # 发送执行统计（summary 内部会通过 sink 自动发送到飞书）
            handler.summary()
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
        .register_p2_card_action_trigger(_on_card_action)
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
