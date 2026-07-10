"""飞书通道 — 通过飞书 Bot 与用户交互。

模块组成：
- client.py   — 飞书 API 客户端（token 管理、消息发送）
- reporter.py — 消息报告器（统一消息发送出口）
- bot.py      — Webhook 服务器 + 事件处理 + Agent 调用
"""

from autops.channels.feishu.bot import run_feishu
from autops.channels.feishu.client import FeishuClient
from autops.channels.feishu.reporter import FeishuReporter

__all__ = ["FeishuClient", "FeishuReporter", "run_feishu"]
