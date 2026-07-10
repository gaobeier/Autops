"""Channels 模块 — 智能体的通信渠道与交互入口。

本模块定义 Agent 与外部交互的通道：
- CLI：命令行交互式对话（channels/cli.py）
- Feishu：飞书 Bot Webhook 通道（channels/feishu/）
- API：HTTP API 接口（可选）
"""

__all__ = ["run_cli", "run_feishu"]


def run_cli() -> None:
    """启动 CLI 交互通道。"""
    from autops.channels.cli import run_cli as _run

    _run()


def run_feishu() -> None:
    """启动飞书 Webhook 通道。"""
    from autops.channels.feishu.bot import run_feishu as _run

    _run()
