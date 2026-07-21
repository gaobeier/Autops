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
| **上下文管理** | 自动总结长对话，防止上下文溢出；统计 token 用量并显示各部分占比（系统提示词/工具/对话消息/其他开销） |
| **长期记忆** | 通过 `workspace/memory/{user_id}/AGENTS.md` 文件持久化跨会话记忆，按用户隔离；Agent 可自主写入重要事实，每次 LLM 调用自动注入到 system prompt |
| **Store 三种长期记忆** | 基于 PostgresStore + pgvector：情景记忆（按用户隔离，存事件）、语义记忆（全局共享，存事实知识）、程序记忆（全局共享，存操作流程）；Agent 通过工具按需查询，支持向量语义搜索 |
| **可观测性** | `AgentObservabilityHandler` 回调处理器跟踪 Turn 号、token 用量、上下文窗口占比；通过 `EventSink` 协议对接各 channel（飞书/CLI） |
| **命令安全** | 三级安全策略：高危（硬编码直接拒绝）、危险（config.yaml 可配，人工审批）、低风险（放行） |
| **人在回路** | `edit_file` 全部审批；`execute` 按安全策略审批；LangGraph Studio 中通过 Resume UI 审批，飞书通道中通过交互式卡片审批 |
| **飞书通道** | 通过飞书 Bot WebSocket 长连接接收消息，支持群聊 @提及、图片和审批卡片交互 |
| **RAGFlow 知识库** | 接入外部 RAGFlow 知识库，Agent 通过 `search_rag_knowledge` 工具检索运维文档、故障方案、操作手册等已沉淀的团队知识 |

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

postgres:
  host: 127.0.0.1
  port: 5432
  user: autops
  password: your_password
  database: autops

store:
  enabled: true                      # 启用 Store 长期记忆（需要 pgvector 扩展）
  embedding:
    model: text-embedding-v4         # 阿里 DashScope embedding 模型
    api_key: sk-xxxxxxxxxxxx         # DASHSCOPE_API_KEY
    base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
    dims: 1024                       # text-embedding-v4 默认 1024 维

ragflow:
  enabled: true                      # 启用 RAGFlow 知识库检索
  api_key: ragflow-xxxxxxxxxxxx      # RAGFlow API Key
  base_url: http://10.200.200.105:13120  # RAGFlow 服务地址
  dataset_ids: []                    # 留空搜索全部知识库，或填入指定知识库 ID
  similarity_threshold: 0.2          # 相似度阈值
  top_k: 5                           # 默认返回条数
```

> PostgreSQL 用于 checkpointer 持久化对话状态。首次启动时在 `public` schema 自动创建 4 张 checkpoint 表。
> 注意：PG 15+ 默认不允许普通用户在 public schema 建表，需 superuser 执行 `ALTER SCHEMA public OWNER TO autops;`。
> Store 长期记忆需要 pgvector 扩展，首次启动时会自动创建 `store` 表和 `store_vectors` 向量索引表。

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
│   ├── middleware/              # 自定义中间件
│   │   ├── memory.py            # AlwaysReloadMemoryMiddleware（每次重读 AGENTS.md）
│   │   └── safety.py            # CommandSafetyMiddleware（高危命令拦截）
│   ├── observability/           # 可观测性模块（Agent 执行监控、Token 统计）
│   │   ├── handler.py            # AgentObservabilityHandler 回调处理器
│   │   └── sink.py               # EventSink 协议（各 channel 实现以接收事件）
│   ├── rag/                     # 外部知识库检索（RAGFlow）
│   │   ├── __init__.py           # 模块导出
│   │   ├── client.py             # RAGFlow SDK 客户端封装
│   │   └── tools.py              # Agent 检索工具（search_rag_knowledge）
│   ├── store/                   # 跨会话长期记忆（PostgresStore + pgvector）
│   │   ├── __init__.py           # Store 初始化与 OpenAI 兼容 Embedding 封装
│   │   ├── episodic.py           # 情景记忆工具（save_event/search_events，按用户隔离）
│   │   ├── semantic.py           # 语义记忆工具（save_knowledge/search_knowledge，全局共享）
│   │   └── procedural.py         # 程序记忆工具（save_procedure/match_procedure，全局共享）
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
| `middleware/` | 自定义 DeepAgents 中间件：`AlwaysReloadMemoryMiddleware`（每次重读 AGENTS.md）、`CommandSafetyMiddleware`（高危命令拦截） |
| `observability/` | Agent 执行可观测性回调：Token 用量、上下文窗口占比、工具调用统计。各 channel 通过实现 `EventSink` 协议接入 |
| `rag/` | 外部知识库检索（RAGFlow SDK）：封装 `search_rag_knowledge` 工具，Agent 按需检索运维文档、故障方案等已沉淀知识 |
| `store/` | 跨会话长期记忆（PostgresStore + pgvector）：episodic（情景，按用户隔离）、semantic（语义，全局）、procedural（程序，全局）。Agent 通过工具按需查询，支持向量语义搜索 |
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
