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
| **互联网搜索** | 基于 Tavily API 搜索技术文档、故障方案、最新资讯 |
| **子智能体** | 将复杂任务委派给具有独立上下文的子 Agent |
| **上下文管理** | 自动总结长对话，防止上下文溢出 |
| **人在回路** | `edit_file`、`write_file`、`execute` 等危险操作执行前暂停；LangGraph Studio 中通过 Resume UI 审批，飞书通道中通过交互式卡片审批 |
| **飞书通道** | 通过飞书 Bot WebSocket 长连接接收消息，支持群聊 @提及、图片和审批卡片交互 |

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

项目使用两个配置文件，均已加入 `.gitignore`：

**`.env`** — 环境变量（LangSmith API Key 等）：

```env
# LangSmith API Key（用于 LangGraph Studio 追踪与调试）
LANGSMITH_API_KEY=lsv2_pt_xxxxxxxxxxxxxxxx

# Tavily API Key（用于互联网搜索工具）
TAVILY_API_KEY=tvly-dev-xxxxxxxxxxxxxxxx
```

**`config.yaml`** — 应用配置（LLM、Agent、飞书参数）：

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
  workspace: ./workspace  # Agent 工作目录限制（默认 ./workspace）

feishu:
  app_id: cli_xxxxxxxxxxxxxxxx
  app_secret: xxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 运行

```bash
# CLI 交互模式（默认）
uv run autops

# 飞书 WebSocket 长连接模式
uv run autops feishu

# LangGraph Dev 模式（提供 API + Studio UI，用于开发调试）
uv run langgraph dev

# 查看帮助
uv run autops --help
```

#### LangGraph Dev 模式

通过 `langgraph dev` 启动开发服务器，提供 REST API 和可视化调试界面：

- **API**：`http://127.0.0.1:2024`
- **Studio UI**：`https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024`
- **API 文档**：`http://127.0.0.1:2024/docs`

如需外部访问，可指定 host 和 port：

```bash
uv run langgraph dev --host 0.0.0.0 --port 2024
```

> 注：`langgraph-cli[inmem]` 已包含在 dev 依赖中，`uv sync` 后即可使用。

#### 飞书通道配置

1. 在[飞书开放平台](https://open.feishu.cn/)创建应用，获取 `App ID` 和 `App Secret`
2. 填入 `config.yaml` 的 `feishu` 部分
3. 在应用「权限管理」中开通以下权限：
   - `im:message` — 发送/接收消息
   - `im:message.patches` — 更新已发送的卡片消息（审批后更新状态用）
   - `im:message.group_at_msg` — 接收群聊 @ 提及
4. 在应用「事件订阅」中选择**「使用长连接接收事件」**（无需公网 URL）
5. 订阅以下事件：
   - `im.message.receive_v1` — 接收消息
   - `card.action.trigger` — 接收卡片按钮回调（审批用）
6. 运行 `uv run autops feishu` 启动服务

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
│       ├── search.py            # 互联网搜索（Tavily API）
│       ├── shell.py             # Shell 命令执行（规划中）
│       ├── system.py            # 系统资源监控（规划中）
│       ├── logs.py              # 日志分析（规划中）
│       ├── docker.py            # Docker 容器管理（规划中）
│       ├── network.py           # 网络诊断（规划中）
│       └── git_ops.py           # Git 操作（规划中）
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
# 安装依赖（含 dev 依赖）
uv sync

# 运行 linter
uv run ruff check src/

# 运行测试
uv run pytest
```

## License

MIT
