"""Tools 模块 — SRE/DevOps 运维工具集。

本模块提供 Agent 可调用的自定义工具：
- search：互联网搜索（基于 Tavily API）
- shell：Shell 命令执行（规划中）
- system：系统资源监控（规划中）
- logs：日志读取与分析（规划中）
- docker：Docker 容器管理（规划中）
- network：网络诊断（规划中）
- git_ops：Git 仓库操作（规划中）
"""

from autops.tools.search import internet_search

__all__ = ["internet_search"]
