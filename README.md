# Autops

> 基于 [Deepagents](https://github.com/langchain-ai/deepagents) 框架的 SRE/DevOps AI Agent 智能体

Autops 是一个面向 SRE（站点可靠性工程）和 DevOps 工作的 AI 智能体。它基于 LangChain 团队维护的 Deepagents 框架构建，能够理解自然语言指令，自主规划任务步骤，并通过工具调用完成运维任务的自动化。

## 功能特性

| 功能 | 说明 |
|------|------|
| **系统监控** | CPU、内存、磁盘、网络状态实时查询 |
| **Shell 执行** | 安全地执行命令行指令并返回结果 |
| **日志分析** | 读取与分析系统/应用日志，快速定位问题 |
| **Docker 管理** | 查看容器状态、启动/停止/重启容器 |
| **网络诊断** | ping、端口检测、DNS 解析 |
| **Git 操作** | 查看仓库状态、分支、最近提交 |
| **子智能体** | 将复杂任务委派给具有独立上下文的子 Agent |
| **上下文管理** | 自动总结长对话，防止上下文溢出 |
| **人在回路** | 危险操作前需人工确认 |
| **飞书通道** | 通过飞书 Bot WebSocket 长连接接收消息，支持群聊 @提及和图片 |

## 技术栈

```
┌─────────────────────────────────────┐
│         Autops (本项目)              │
│  agents / channels / tools / prompts │
├─────────────────────────────────────┤
│         Deepagents 0.6.x             │  ← 完整框架：规划、上下文管理、子智能体
├─────────────────────────────────────┤
│         LangGraph                    │  ← 图运行时
├─────────────────────────────────────┤
│         LangChain                    │  ← 模型抽象与工具协议
└─────────────────────────────────────┘
```

## 快速开始

### 环境要求

- Python >= 3.13
- [uv](https://docs.astral.sh/uv/) 包管理器

### 安装

```bash
# 克隆项目后，使用 uv 安装依赖
uv sync
```

### 配置

在项目根目录创建 `config.yaml` 文件（参考 `config.yaml` 示例）：

```yaml
# 全局日志级别: DEBUG / INFO / WARNING / ERROR
log_level: INFO

llm:
  provider: openai
  model: qwen3.7-plus
  api_key: sk-xxxxxxxxxxxx
  base_url: https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1
  temperature: 0.7
  max_tokens: 4096

agent:
  max_iterations: 15
  recursion_limit: 100
  # workspace: /path/to/workspace  # Agent 工作目录限制（留空则使用项目根目录）

feishu:
  app_id: cli_xxxxxxxxxxxxxxxx
  app_secret: xxxxxxxxxxxxxxxxxxxxxxxxxx
  webhook_host: 0.0.0.0
  webhook_port: 8080
```

### 运行

```bash
# CLI 交互模式（默认）
uv run autops

# 飞书 WebSocket 长连接模式
uv run autops feishu

# 查看帮助
uv run autops --help
```

#### 飞书通道配置

1. 在[飞书开放平台](https://open.feishu.cn/)创建应用，获取 `App ID` 和 `App Secret`
2. 填入 `config.yaml` 的 `feishu` 部分
3. 在应用「事件订阅」中选择**「使用长连接接收事件」**（无需公网 URL）
4. 订阅 `im.message.receive_v1` 事件
5. 运行 `uv run autops feishu` 启动服务
ngrok http 8080
```

## 项目结构

```
autops/
├── src/autops/
│   ├── __init__.py              # 包初始化
│   ├── agents/                  # 智能体定义（主 Agent + 子 Agent）
│   ├── channels/                # 通信渠道（CLI / 飞书 Webhook）
│   │   ├── cli.py               # CLI 交互入口
│   │   └── feishu/              # 飞书 Bot 通道（WebSocket 长连接）
│   │       ├── client.py        # 飞书 API 客户端（token、消息发送）
│   │       ├── reporter.py      # 消息报告器
│   │       └── bot.py           # Webhook 服务器 + 事件处理
│   ├── config/                  # 全局配置与环境管理
│   ├── llm/                     # LLM 客户端封装
│   ├── prompts/                 # 系统提示词与 Jinja2 模板
│   │   ├── renderer.py          # 模板渲染引擎
│   │   ├── system.py            # 提示词构建函数
│   │   └── templates/           # .j2 模板文件
│   │       └── main_agent.j2    # 主 Agent 系统提示词模板
│   └── tools/                   # SRE/DevOps 运维工具集
│       ├── shell.py             # Shell 命令执行
│       ├── system.py            # 系统资源监控
│       ├── logs.py              # 日志分析
│       ├── docker.py            # Docker 容器管理
│       ├── network.py           # 网络诊断
│       └── git_ops.py           # Git 操作
├── pyproject.toml
├── config.yaml                 # 配置文件（LLM、Agent 参数）
├── CODEBUDDY.md                 # CodeBuddy 项目指令
└── README.md
```

### 模块说明

| 模块 | 职责 |
|------|------|
| `agents/` | 基于 `create_deep_agent` 创建主 Agent 和子 Agent，定义编排逻辑 |
| `channels/` | 定义 Agent 与用户交互的入口：CLI 对话、飞书 Webhook |
| `config/` | 从 `config.yaml` 加载配置，管理模型参数和运行时选项 |
| `llm/` | 封装 LangChain 聊天模型客户端，支持多模型切换 |
| `prompts/` | 使用 Jinja2 模板（`.j2`）管理系统提示词，支持变量渲染 |
| `tools/` | 自定义工具函数，供 Agent 通过 function calling 调用 |

## 使用示例

```
> 检查服务器健康状况
> 查看正在运行的 Docker 容器
> 分析 /var/log/nginx/error.log 最近的错误
> ping 一下 8.8.8.8 看网络通不通
> 查看当前 Git 仓库状态
> 磁盘空间不足了，帮我看看哪些目录占用最大
```

## 开发

```bash
# 安装开发依赖
uv sync --extra dev

# 运行 linter
uv run ruff check src/

# 运行测试
uv run pytest
```

## License

MIT
