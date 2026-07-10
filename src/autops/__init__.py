"""Autops — 基于 Deepagents 框架的 SRE/DevOps AI Agent 智能体。"""

from __future__ import annotations

import sys

__version__ = "0.1.0"


def main() -> None:
    """程序入口 — 根据参数选择通道。

    用法:
        autops          # CLI 交互模式（默认）
        autops feishu   # 飞书 Webhook 模式
    """
    channel = sys.argv[1] if len(sys.argv) > 1 else "cli"

    if channel == "feishu":
        from autops.channels.feishu.bot import run_feishu

        run_feishu()
    elif channel in ("--help", "-h", "help"):
        print("用法: autops [channel]")
        print()
        print("通道:")
        print("  (无参数)  CLI 交互模式")
        print("  feishu    飞书 Webhook 模式")
    else:
        from autops.channels.cli import run_cli

        run_cli()
