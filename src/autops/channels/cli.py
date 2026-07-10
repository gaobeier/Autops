"""CLI 交互通道 — 命令行对话入口。"""

from __future__ import annotations

import sys

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from autops.agents.main_agent import create_main_agent
from autops.config.settings import config

console = Console()


def run_cli() -> None:
    """启动交互式 CLI 对话。"""
    # 打印欢迎信息
    console.print(
        Panel.fit(
            "[bold cyan]Autops[/bold cyan] — SRE/DevOps AI Agent\n"
            f"模型: [dim]{config.llm.model}[/dim]  "
            f"输入 [bold]exit[/bold] 或 [bold]quit[/bold] 退出",
            border_style="cyan",
        )
    )

    # 创建 Agent
    console.print("[dim]正在初始化 Agent...[/dim]")
    agent = create_main_agent()
    console.print("[green]Agent 就绪，开始对话吧！[/green]\n")

    # 多轮对话循环
    messages: list[dict] = []
    while True:
        try:
            user_input = Prompt.ask("[bold green]你[/bold green]")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]再见！[/yellow]")
            break

        if user_input.strip().lower() in ("exit", "quit", "q"):
            console.print("[yellow]再见！[/yellow]")
            break

        if not user_input.strip():
            continue

        # 调用 Agent
        messages.append({"role": "user", "content": user_input})
        try:
            result = agent.invoke(
                {"messages": messages},
                config={"recursion_limit": config.agent.recursion_limit},
            )
            # 提取最后一条 AI 回复
            ai_messages = result.get("messages", [])
            if ai_messages:
                last = ai_messages[-1]
                reply = last.content if hasattr(last, "content") else str(last)
                console.print()
                console.print(
                    Panel(
                        str(reply),
                        title="[bold cyan]Autops[/bold cyan]",
                        border_style="cyan",
                    )
                )
                # 更新消息历史
                messages = [
                    {"role": m.type, "content": m.content}
                    if hasattr(m, "type")
                    else {"role": "assistant", "content": str(m)}
                    for m in ai_messages
                ]
        except Exception as e:  # noqa: BLE001
            console.print(f"[red]错误: {e}[/red]")
        console.print()
