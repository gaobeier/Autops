# Learn DeepAgents

> Deepagents 框架使用经验与知识沉淀

## 上下文管理与压缩机制

### Context 会不会爆炸？

**不会。** Deepagents 默认启用 `SummarizationMiddleware`（在 `create_deep_agent` 内部自动添加），当对话 token 达到阈值时自动压缩。

### 三层压缩机制

```
对话持续增长
      ↓
① Truncate Args（工具参数截断）—— 最先触发
      ↓  将旧消息中 write_file/edit_file 的大参数截断
      ↓
② Summarization（对话摘要）—— token 进一步超限触发
      ↓  用 LLM 对旧消息生成摘要，替换原始消息
      ↓  完整历史 offload 到文件系统
      ↓
③ ContextOverflowError fallback（兜底）
      ↓  如果 API 返回超限错误，强制摘要后重试
```

### 1. Truncate Args（工具参数截断）

**先于摘要触发**，只截断旧消息中工具调用的参数（如 `write_file` 的大段内容），保留最近的消息不动。

```python
"truncate_args_settings": {
    "trigger": ("messages", 20),   # 20 条消息时触发
    "keep": ("messages", 20),      # 保留最近 20 条不动
    "max_length": 2000,            # 参数截断到 2000 字符
    "truncation_text": "...(truncated)"
}
```

### 2. Summarization（对话摘要）

当 token 达到阈值时，用 LLM 对**旧消息**生成摘要，替换原始消息：

```python
{
    "trigger": ("fraction", 0.85),  # 上下文窗口的 85% 时触发
    "keep": ("fraction", 0.10),     # 保留最近 10% 的消息不动
}
```

**流程**：
1. 识别需要摘要的旧消息（排除 `keep` 范围内的最近消息）
2. 调用 LLM 对旧消息生成摘要
3. 将完整旧消息 offload 到 `/conversation_history/{thread_id}.md`
4. 用摘要 HumanMessage 替换旧消息
5. 摘要中嵌入 offload 文件路径，Agent 可通过 `read_file` 回溯

### 3. ContextOverflowError Fallback

如果 API 直接返回 context 超限错误，中间件会**强制摘要并重试**，而不是报错。

### 默认阈值（自动选择）

| 模型类型 | trigger | keep | truncate_args trigger |
|---------|---------|------|----------------------|
| 有 profile（如 GPT-4o） | `fraction 0.85` | `fraction 0.10` | `fraction 0.85` |
| 无 profile（如 qwen） | `tokens 170000` | `messages 6` | `messages 20` |

> qwen3.7-plus 没有注册 harness profile，使用固定阈值：170K token 触发摘要，保留最近 6 条消息。

### 手动触发压缩

`SummarizationToolMiddleware` 提供 `compact_conversation` 工具，Agent 可主动调用压缩：

```python
from deepagents.middleware.summarization import SummarizationToolMiddleware

agent = create_deep_agent(
    middleware=[SummarizationToolMiddleware(summ_middleware)],
)
```

## Checkpointer 持久化

### Checkpointer 如何加载历史上下文

当用户发送新消息时，`agent.invoke({"messages": [user_msg]}, config={"thread_id": ...})` 的完整流程：

```
用户发新消息 "hello，我是谁"
         ↓
agent.invoke(messages=[user_msg], config={"thread_id": "oc_xxx_ou_xxx"})
         ↓
LangGraph 从 PostgresSaver 加载该 thread_id 的最新 checkpoint
         ↓
从 checkpoint.channel_versions 获取 messages 通道的版本号
         ↓
根据版本号从 checkpoint_writes 表按时间顺序解码所有历史消息
         ↓
重建完整消息列表: [HumanMessage("你好我是Gordon"),
                  AIMessage("你好 Gordon！..."),
                  HumanMessage("hello，我是谁")]   ← 新消息追加在末尾
         ↓
将完整消息列表发送给 LLM
         ↓
LLM 响应后，将新的 AIMessage 写入 checkpoint_writes
         ↓
创建新的 checkpoint（parent 指向上一个 checkpoint）
```

**关键点**：
1. **不传完整历史**：`invoke` 只传新消息，旧消息由 checkpointer 自动加载
2. **版本号引用**：checkpoint 存版本号而非消息内容，通过版本号找到 `checkpoint_writes` 中的 blob
3. **增量写入**：每次 LLM/工具调用结果追加到 `checkpoint_writes`，不修改旧记录
4. **链式结构**：每个 checkpoint 的 `parent_checkpoint_id` 指向上一个，形成可回溯的链

**checkpoint 链示例**：
```
step=-1 (input)  → 用户发消息，创建初始 checkpoint
step=0  (loop)   → Agent 循环第 1 步（如中间件处理）
step=1  (loop)   → LLM 调用
step=2  (loop)   → 工具调用
step=3  (loop)   → LLM 处理工具结果
step=4  (loop)   → 生成回复
step=5  (input)  → 用户发第 2 条消息（parent 指向 step 4）
step=6  (loop)   → 第 2 轮 LLM 调用
...
```

### PostgresSaver 表结构

| 表 | 作用 |
|---|------|
| `checkpoints` | 检查点主表，存储状态快照（JSONB）+ 元数据 |
| `checkpoint_blobs` | 大对象存储（msgpack 编码的消息内容） |
| `checkpoint_writes` | 写入操作日志（每步 LLM/工具调用的中间写入） |
| `checkpoint_migrations` | 迁移版本记录 |

### 消息存储方式

- `checkpoints.checkpoint` (JSONB)：只存版本号引用，不存消息明文
- `checkpoint_writes.blob` (bytea)：存 msgpack 编码的消息内容
- 解码用 `JsonPlusSerializer.loads_typed((type, blob))`

### 会话隔离

通过 `thread_id` 区分会话（飞书场景：`chat_id + user_id`），不同会话的 checkpoint 互不干扰。

## LocalShellBackend 工作目录限制

```python
LocalShellBackend(
    root_dir=str(workspace),   # 工作目录根
    virtual_mode=True,         # 路径相对于 root_dir
    timeout=120,
    max_output_bytes=100_000,
)
```

- `virtual_mode=True`：Agent 的文件操作路径 `/test.txt` 映射到 `root_dir/test.txt`
- `virtual_mode` 限制文件系统工具（read/write/ls/grep），不限制 Shell 命令本身
- 如需限制 Shell，需用 `interrupt_on` 启用 Human-in-the-Loop 审批

## permissions 与 Shell backend 的限制

`FilesystemPermission` **不支持**带 Shell 执行的 backend（`LocalShellBackend`）：
```
NotImplementedError: FilesystemMiddleware does not yet support permissions
with backends that provide command execution
```
只能用 `virtual_mode` 限制文件路径，不能用 `permissions` 做细粒度控制。

## 自动注册的中间件

`create_deep_agent` 内部自动添加：

1. **SummarizationMiddleware** — 上下文压缩
2. **SubAgentMiddleware** — 子智能体委派
3. **FilesystemMiddleware** — 文件系统工具（read/write/edit/ls/grep/glob）
4. **HumanInTheLoopMiddleware** — 人在回路审批（如果配置了 `interrupt_on`）
5. **PatchToolCallsMiddleware** — 工具调用修补
6. **TodoListMiddleware** — 任务清单管理

可通过 `middleware` 参数覆盖或 `_excluded_middleware` 排除。

## 模型 Profile

```python
# 检查模型是否有 profile
model.profile  # dict or None
model.profile.get("max_input_tokens")  # 上下文窗口大小
```

有 profile 的模型（GPT-4o、Claude 等）使用 fraction 阈值；无 profile 的模型（qwen 等）使用固定 token 阈值。

可注册自定义 profile：
```python
from deepagents import register_harness_profile
```

## Plan-Execute 机制

Deepagents 的 plan-execute 不是独立的规划器+执行器架构，而是通过 **TodoListMiddleware + 系统提示词 + SubAgent** 三者协作实现。

### 三层协作

```
用户请求: "检查服务器状态并修复磁盘问题"
    ↓
① Plan（规划）—— TodoListMiddleware 的 write_todos 工具
    LLM 自主决定是否需要规划（≥3 步才用）
    调用 write_todos 工具，创建任务清单:
    [
      {content: "检查磁盘使用情况", status: "in_progress"},
      {content: "识别大文件目录",   status: "pending"},
      {content: "清理临时文件",     status: "pending"},
    ]
    ↓
② Execute（执行）—— LangGraph Agent 循环
    每轮循环: LLM 调用工具（ls/execute/read_file...）→ 工具返回结果 → 更新状态
    完成一个任务后，调用 write_todos 更新状态:
    [
      {content: "检查磁盘使用情况", status: "completed"},
      {content: "识别大文件目录",   status: "in_progress"},
      {content: "清理临时文件",     status: "pending"},
    ]
    ↓
③ Delegate（委派）—— SubAgentMiddleware 的 task 工具
    主 Agent 可将子任务委派给子 Agent:
    task(description="分析 /var/log 下的日志", subagent_type="log_analyzer")
    子 Agent 有独立上下文窗口，执行完返回结果给主 Agent
```

### TodoListMiddleware 详解

**来源**：`langchain.agents.middleware.TodoListMiddleware`（非 Deepagents 独有）

**核心机制**：
1. 注册 `write_todos` 工具（Agent 通过 tool calling 调用）
2. `wrap_model_call`：在系统提示词中注入规划指导
3. `after_model`：检测并阻止并行调用 `write_todos`（每轮只能更新一次）
4. 状态存储在 `PlanningState.todos` 字段（通过 checkpointer 持久化）

**Todo 结构**：
```python
class Todo(TypedDict):
    content: str                          # 任务描述
    status: Literal["pending", "in_progress", "completed"]  # 状态
```

**write_todos 工具行为**：
```python
def write_todos(todos: list[Todo]) -> Command:
    return Command(update={
        "todos": todos,           # 替换整个任务列表（非追加）
        "messages": [ToolMessage(f"Updated todo list to {todos}")],
    })
```
每次调用**替换整个列表**，不是增量更新。

**何时规划（系统提示词指导）**：
- ≥3 个步骤的复杂任务 → 使用 write_todos
- <3 步的简单任务 → 直接执行，不用 write_todos
- 用户明确要求规划时 → 使用 write_todos

### SubAgent 委派机制

**来源**：`deepagents.middleware.subagents.SubAgentMiddleware`

主 Agent 通过 `task` 工具委派子任务：

```python
from deepagents import SubAgent

subagents = [
    SubAgent(
        name="log_analyzer",          # 子 Agent 名称
        description="分析日志文件",     # 主 Agent 据此决定何时委派
        system_prompt="你是一个日志分析专家...",  # 独立提示词
        tools=[read_file, grep],      # 独立工具集（可选）
        # model="openai:gpt-4o-mini", # 可用不同模型（可选）
    ),
]

agent = create_deep_agent(
    model="...",
    subagents=subagents,  # 自动注册 SubAgentMiddleware + task 工具
)
```

**子 Agent 特点**：
- **独立上下文窗口**：不消耗主 Agent 的 token 配额
- **独立工具集**：可以限制子 Agent 的能力
- **独立模型**：可以用更便宜的模型执行子任务
- **结果返回**：子 Agent 执行完后，结果以 ToolMessage 返回给主 Agent

### Plan-Execute 与传统 ReAct 的区别

| 特性 | 传统 ReAct | Deepagents Plan-Execute |
|------|-----------|------------------------|
| 规划 | 无显式规划，逐步反应 | LLM 自主决定是否用 write_todos 规划 |
| 状态追踪 | 无 | todos 列表持久化到 checkpointer |
| 任务委派 | 不支持 | SubAgent 独立上下文执行子任务 |
| 复杂任务 | 容易迷失方向 | todo 列表 + 子 Agent 避免上下文爆炸 |
| 简单任务 | 直接执行 | 也直接执行（不强制规划） |

**关键设计**：规划是**可选的**。LLM 根据任务复杂度自主决定是否调用 `write_todos`，简单任务直接执行不浪费 token。

## 记忆体系

Deepagents 有三层记忆，分别对应不同的时间跨度和存储方式：

```
┌─────────────────────────────────────────────────────┐
│                  记忆体系总览                         │
├──────────┬──────────────┬──────────┬────────────────┤
│  层级     │  存储         │  生命周期 │  实现组件       │
├──────────┼──────────────┼──────────┼────────────────┤
│ 短期记忆  │ PostgresSaver │  会话级   │ checkpointer   │
│          │ (PG 表)       │  跨请求   │                │
├──────────┼──────────────┼──────────┼────────────────┤
│ 工作记忆  │ AgentState    │  单次任务 │ write_todos    │
│          │ (todos 字段)  │  执行中   │ + SubAgent     │
├──────────┼──────────────┼──────────┼────────────────┤
│ 长期记忆  │ AGENTS.md     │  跨会话   │ MemoryMiddleware│
│          │ (文件系统)     │  永久     │ + edit_file    │
└──────────┴──────────────┴──────────┴────────────────┘
```

### 短期记忆 — Checkpointer

- **存储**：PostgreSQL（`checkpoints` / `checkpoint_writes` 表）
- **内容**：对话消息历史（HumanMessage / AIMessage / ToolMessage）
- **生命周期**：会话级，通过 `thread_id` 隔离，进程重启不丢失
- **机制**：每次 `agent.invoke()` 自动加载历史 + 保存新状态
- **压缩**：超过阈值自动摘要（SummarizationMiddleware）

### 工作记忆 — TodoList + SubAgent

- **存储**：Agent 运行时状态（`PlanningState.todos`）
- **内容**：当前任务清单 + 子 Agent 的独立上下文
- **生命周期**：单次任务执行中，随 checkpointer 持久化
- **机制**：
  - `write_todos` 工具管理任务进度
  - `task` 工具委派子任务给 SubAgent（独立上下文窗口）
  - 子 Agent 结果以 ToolMessage 返回

### 长期记忆 — AGENTS.md 文件

- **存储**：文件系统中的 Markdown 文件（`AGENTS.md`）
- **内容**：项目知识、用户偏好、经验教训、工作流程
- **生命周期**：永久，跨会话持久
- **实现**：`MemoryMiddleware`

#### 使用方式

```python
agent = create_deep_agent(
    model="...",
    memory=[
        "~/.deepagents/AGENTS.md",     # 全局记忆（用户级）
        "./.deepagents/AGENTS.md",      # 项目级记忆
        "/memory/ops_knowledge.md",     # 自定义记忆文件
    ],
)
```

#### 加载机制

1. `MemoryMiddleware` 启动时从指定路径读取 AGENTS.md 文件
2. 将文件内容注入系统提示词的 `<agent_memory>` 标签中
3. 每次 LLM 调用时，记忆内容作为系统提示词的一部分发送
4. 支持 Anthropic prompt caching（`add_cache_control=True`）

#### 记忆更新

Agent 通过 `edit_file` 工具**自主更新**记忆文件：

```
用户: "记住我的服务器 IP 是 192.168.1.100"
    ↓
Agent 调用 edit_file 修改 AGENTS.md
    追加: "用户服务器 IP: 192.168.1.100"
    ↓
下次会话 MemoryMiddleware 加载更新后的 AGENTS.md
    → Agent 知道服务器 IP 了
```

#### 系统提示词指导何时更新记忆

**应该记忆**：
- 用户明确要求记住的信息（"记住我的邮箱"）
- 用户描述的角色或行为偏好（"你是一个 Web 研究员"）
- 用户对工作的反馈（什么做错了、如何改进）
- 工具使用所需信息（Slack 频道 ID、邮箱地址）
- 新发现的模式或偏好（编码风格、约定、工作流）

**不应记忆**：
- 临时/短暂信息（"我在用手机"）
- 一次性任务请求（"帮我找个菜谱"）
- 简单问答（"今天几号？"）
- 寒暄/确认（"好的！"、"谢谢"）
- **永远不存储 API key / 密码 / 凭证**

#### AGENTS.md 文件格式

标准 Markdown，无强制结构。常见章节：
```markdown
# 项目概述
...

# 构建/测试命令
- `uv run pytest`
- `uv run ruff check src/`

# 代码风格
- 使用 ruff，行宽 100
- 类型注解必填

# 用户偏好
- 邮箱: john@example.com
- 服务器 IP: 192.168.1.100
```

HTML 注释 `<!-- ... -->` 会在注入系统提示词前被移除。

### 三层记忆协作

```
用户: "检查服务器 192.168.1.100 的磁盘问题"
    ↓
长期记忆 (AGENTS.md): "用户的服务器 IP 是 192.168.1.100"
    → Agent 知道目标服务器
    ↓
短期记忆 (checkpointer): 之前对话讨论过磁盘告警
    → Agent 知道上下文
    ↓
工作记忆 (write_todos): [
    "SSH 连接服务器",          ← completed
    "检查磁盘使用情况",        ← in_progress
    "识别大文件",              ← pending
    "清理临时文件",            ← pending
  ]
    → Agent 知道当前进度
    ↓
Agent 执行，完成后用 edit_file 更新 AGENTS.md:
    "服务器 192.168.1.100 的 /var/log 目录需要定期清理"
    → 转为长期记忆
```

### Store — 跨会话共享的键值存储

`store` 参数不是第四层记忆，而是 **LangGraph 的 BaseStore**，一种**跨会话共享的持久化键值存储**。

#### Store vs 其他记忆的区别

| 组件 | 存储类型 | 作用域 | 特点 |
|------|---------|--------|------|
| checkpointer | 对话状态 | 单会话 (thread_id) | 自动加载/保存消息历史 |
| AGENTS.md (memory) | 系统提示词 | 全局 | 始终注入到每次 LLM 调用 |
| **store** | **键值对 (key-value)** | **跨会话共享** | **按 namespace 隔离，支持语义搜索** |

#### Store 的核心能力

```python
from langgraph.store.memory import InMemoryStore
# 或 from langgraph.store.postgres import PostgresStore

store = InMemoryStore()

agent = create_deep_agent(
    model="...",
    store=store,  # 传入 BaseStore 实例
)
```

Store 提供 API：
- `put(namespace, key, value)` — 存储数据
- `get(namespace, key)` — 读取数据
- `search(namespace, query)` — 语义搜索（需要配置 index）
- `delete(namespace, key)` — 删除数据
- `list_namespaces()` — 列出命名空间

#### Store 在 Deepagents 中的用途

1. **StoreBackend**：作为文件系统后端的替代，文件存储在 Store 中而非磁盘

   ```python
   from deepagents.backends import StoreBackend

   backend = StoreBackend(
       store=my_store,
       namespace=lambda rt: (rt.server_info.user.identity, "filesystem"),
   )
   agent = create_deep_agent(model="...", backend=backend)
   ```

   - 文件按 namespace 隔离（如按用户 ID）
   - 跨会话共享文件（不同 thread 的 Agent 能访问同一文件）
   - 适合多用户/多 Agent 场景

2. **跨会话数据共享**：不同会话的 Agent 可以通过 Store 共享数据

   ```
   会话 A (thread_id=xxx): Agent 存储分析结果 → store.put(("reports",), "disk_analysis", {...})
   会话 B (thread_id=yyy): Agent 读取分析结果 → store.get(("reports",), "disk_analysis")
   ```

3. **语义搜索**（可选）：配置 index 后支持向量搜索

   ```python
   store = PostgresStore(
       conn_string="...",
       index={
           "dims": 1536,
           "fields": ["content"],
           "embed": "openai:text-embedding-3-small",
       },
   )
   # Agent 可以用 store.search(("knowledge",), "磁盘空间不足") 搜索相关记忆
   ```

#### Store vs AGENTS.md

| 特性 | AGENTS.md (memory) | Store |
|------|-------------------|-------|
| 数据格式 | Markdown 文本 | 任意 JSON/键值对 |
| 加载方式 | 全量注入系统提示词 | 按需读取（Agent 用工具查询） |
| 适合场景 | 项目知识、用户偏好 | 结构化数据、跨会话共享 |
| 语义搜索 | 不支持 | 支持（配置 index） |
| 更新方式 | edit_file 修改文件 | put/delete API |
| 占用 token | 始终占用（在提示词中） | 按需加载（不占提示词） |

#### 当前项目状态

Autops 项目目前**未使用 store**，长期记忆通过 AGENTS.md (memory 参数) 实现。如需跨会话共享结构化数据（如多个用户的运维知识库），可以配置 `store=PostgresStore(...)`。

### Store 的触发机制

**Store 没有自动触发机制**。与 checkpointer（自动加载/保存）和 memory（自动注入提示词）不同，Store 的读写完全由**自定义工具**驱动，Agent 通过 tool calling 主动操作。

#### 三种记忆的触发方式对比

| 记忆类型 | 触发方式 | 自动/手动 |
|---------|---------|----------|
| checkpointer | `agent.invoke()` 时自动加载/保存 | **自动** |
| memory (AGENTS.md) | `MemoryMiddleware` 启动时自动加载，注入提示词 | **自动** |
| **store** | **Agent 调用带 `InjectedStore` 的自定义工具** | **手动（工具驱动）** |

#### 如何让 Agent 使用 Store

需要**自定义工具**，通过 `InjectedStore` 注入 store 实例：

```python
from typing import Annotated
from langgraph.prebuilt import InjectedStore
from langgraph.store.base import BaseStore
from langchain_core.tools import tool

@tool
def save_knowledge(
    key: str,
    content: str,
    store: Annotated[BaseStore, InjectedStore()],
) -> str:
    """保存运维知识到知识库。"""
    store.put(("ops_knowledge",), key, {"content": content})
    return f"已保存知识: {key}"

@tool
def search_knowledge(
    query: str,
    store: Annotated[BaseStore, InjectedStore()],
) -> str:
    """搜索运维知识库。"""
    results = store.search(("ops_knowledge",), query)
    if not results:
        return "未找到相关知识"
    return "\n".join(
        f"[{item.key}] {item.value.get('content', '')[:200]}"
        for item in results
    )

agent = create_deep_agent(
    model="...",
    tools=[save_knowledge, search_knowledge],
    store=PostgresStore(conn_string="..."),
)
```

#### 关键点

1. **`InjectedStore()` 注入**：store 实例通过依赖注入传给工具，**对 LLM 不可见**（LLM 只看到 `key` 和 `content` 参数，看不到 `store` 参数）
2. **Agent 自主决策**：LLM 根据对话上下文决定是否调用 `save_knowledge` / `search_knowledge` 工具
3. **namespace 隔离**：通过 namespace 元组（如 `("ops_knowledge",)`）分类管理不同类型的数据

#### 实际触发流程

```
用户: "记一下，生产环境 192.168.1.100 的磁盘需要每周清理"
    ↓
LLM 判断: 这是值得保存的运维知识
    ↓
LLM 调用工具: save_knowledge(key="disk_cleanup_192.168.1.100",
                             content="生产环境 192.168.1.100 的磁盘需要每周清理")
    ↓
工具执行: store.put(("ops_knowledge",), "disk_cleanup_192.168.1.100", {...})
    ↓
返回: "已保存知识: disk_cleanup_192.168.1.100"
```

```
用户（另一个会话）: "192.168.1.100 服务器有什么运维注意事项？"
    ↓
LLM 判断: 需要查询知识库
    ↓
LLM 调用工具: search_knowledge(query="192.168.1.100 运维")
    ↓
工具执行: store.search(("ops_knowledge",), "192.168.1.100 运维")
    ↓
返回: "[disk_cleanup_192.168.1.100] 生产环境磁盘需要每周清理"
    ↓
LLM: "192.168.1.100 的磁盘需要每周清理（来自知识库）"
```

#### 语义搜索配置

Store 的 `search` 默认是精确匹配。要支持语义搜索（向量检索），需要在创建 store 时配置 index：

```python
store = PostgresStore(
    conn_string="postgresql://...",
    index={
        "dims": 1536,                          # 向量维度
        "fields": ["content"],                  # 对哪些字段建索引
        "embed": "openai:text-embedding-3-small",  # embedding 模型
    },
)
# 之后 store.search(("ops_knowledge",), "磁盘空间不足")
# 会语义匹配到 "磁盘需要每周清理" 的记录
```

#### Store vs Memory 适用场景

| 场景 | 推荐方案 | 原因 |
|------|---------|------|
| 项目编码规范 | AGENTS.md | 始终在提示词中，每次都生效 |
| 用户个人偏好 | AGENTS.md | 量少，始终需要 |
| 运维知识库（100+ 条目） | Store | 量大，按需查询不占 token |
| 多用户共享数据 | Store | 按 namespace 隔离 |
| 历史故障分析记录 | Store | 需要语义搜索 |
| 跨会话任务协作 | Store | 不同 thread 共享数据 |

### Store 与 RAG 的区别

Store 配置了 `index` 后确实支持向量语义搜索，看起来像 RAG，但两者定位和架构不同。

#### 本质区别

| 维度 | Store | 传统 RAG |
|------|-------|---------|
| **定位** | Agent 的持久化键值存储 | 检索增强生成的完整流水线 |
| **数据写入** | Agent 通过工具主动 `put` | 离线 ETL：文档→分块→embedding→向量库 |
| **检索触发** | Agent 自主决定调用工具查询 | 每次 LLM 调用前自动检索 |
| **检索结果** | 返回给 Agent 作为工具结果 | 直接拼接到 LLM 提示词中 |
| **数据结构** | namespace + key + value（JSON） | chunk + embedding + metadata |
| **分块策略** | 不分块，整条存储 | 有分块策略（固定长度/语义分块/递归分块） |
| **向量索引** | 可选（配置 index） | 核心（必须有向量索引） |
| **重排序** | 不支持 | 通常配合 reranker |
| **框架** | LangGraph 内置 | LangChain / LlamaIndex 独立 pipeline |

#### 架构对比

```
传统 RAG 流水线:
┌─────────────────────────────────────────────────┐
│ 离线阶段                                         │
│  文档 → 加载 → 分块 → embedding → 向量数据库      │
│                          ↓                       │
│ 在线阶段（每次用户提问自动触发）                    │
│  用户问题 → embedding → 向量搜索 → top-K chunks   │
│           → 拼接到提示词 → LLM 生成回答            │
└─────────────────────────────────────────────────┘
  特点: 自动检索，Agent 不决定是否检索

Store 流水线:
┌─────────────────────────────────────────────────┐
│ 写入阶段（Agent 自主决定）                        │
│  Agent 调用 save_knowledge 工具                   │
│    → store.put(namespace, key, value)            │
│    → (可选) 自动 embedding 存入向量索引            │
│                                                  │
│ 查询阶段（Agent 自主决定）                        │
│  Agent 调用 search_knowledge 工具                 │
│    → store.search(namespace, query)              │
│    → (可选) 向量语义搜索                           │
│    → 结果作为 ToolMessage 返回给 Agent            │
│    → Agent 决定如何使用结果                        │
└─────────────────────────────────────────────────┘
  特点: Agent 决定是否检索、何时检索、如何使用结果
```

#### 关键差异

1. **检索的主动性**
   - RAG：**自动检索**，每次 LLM 调用前都检索，用户无感
   - Store：**Agent 自主检索**，LLM 判断需要时才调用工具查询

2. **数据处理**
   - RAG：有完整的文档处理流水线（加载→分块→embedding）
   - Store：存储的是 Agent 写入的结构化数据，不分块

3. **结果使用**
   - RAG：检索结果**自动拼接到提示词**，LLM 直接看到
   - Store：检索结果作为**工具返回值**，Agent 决定是否引用

4. **适用场景**
   - RAG：大量非结构化文档（PDF、网页、手册），用户提问自动检索
   - Store：Agent 运行时积累的经验/知识，按需查询

#### 何时用哪个

| 场景 | 推荐 | 原因 |
|------|------|------|
| 搜索 1000 页运维手册 | RAG | 非结构化文档，需分块+自动检索 |
| Agent 积累的故障处理经验 | Store | 结构化数据，Agent 自主管理 |
| 用户上传 PDF 提问 | RAG | 文档检索场景 |
| 多 Agent 共享运维知识 | Store | 跨会话共享，按需查询 |
| 代码库智能问答 | RAG | 大量代码文件，需自动检索 |
| Agent 记住用户服务器配置 | Store | 少量结构化数据 |

#### 可以结合使用

```
运维手册（PDF/HTML）→ RAG pipeline → 向量数据库
                                        ↓
Agent 运行时:                            │
  1. 用户: "nginx 配置怎么优化？"         │
  2. Agent 调用 RAG 检索工具 ─────────────┘ → 返回手册片段
  3. Agent 调用 Store 查询 → 返回历史优化经验
  4. Agent 综合两者 → 生成回答
  5. Agent 调用 save_knowledge → 存入 Store 供下次使用
```

**总结**：Store 是 Agent 的"记忆本"，Agent 自主读写；RAG 是"搜索引擎"，自动检索外部文档。两者互补，不是替代关系。

## Deepagents 接入 RAG

Deepagents 框架**没有内置 RAG 模块**。接入 RAG 的方式是**自定义检索工具**，Agent 通过 tool calling 按需检索。

### 核心思路

RAG 在 Deepagents 中就是一个普通工具：

```
用户提问 → LLM 判断需要检索 → 调用 rag_search 工具 → 返回文档片段 → LLM 生成回答
```

与 Store 的 `search_knowledge` 工具形式完全一样，区别在于后端实现：
- Store：从 LangGraph BaseStore 查询
- RAG：从向量数据库（Chroma/FAISS/PGVector）检索

### 方式一：LangChain Retriever 工具（最简单）

LangChain 已有 `create_retriever_tool`，直接作为 Deepagents 的工具传入：

```python
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain.tools.retriever import create_retriever_tool

# 1. 准备向量数据库
embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small",
    api_key="sk-xxx",
    base_url="https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
)
vectorstore = Chroma(
    persist_directory="./chroma_db",
    embedding_function=embeddings,
    collection_name="ops_docs",
)

# 2. 创建检索工具
retriever_tool = create_retriever_tool(
    retriever=vectorstore.as_retriever(search_kwargs={"k": 5}),
    name="search_ops_docs",
    description=(
        "搜索运维知识库，包含运维手册、SOP 文档、故障处理案例等。"
        "当用户询问运维操作、配置方法、故障排查时使用此工具。"
    ),
)

# 3. 接入 Agent
agent = create_deep_agent(
    model=create_llm(),
    tools=[retriever_tool],  # 作为普通工具传入
    system_prompt=get_main_agent_prompt(),
    backend=backend,
    checkpointer=checkpointer,
)
```

### 方式二：自定义 RAG 工具（更灵活）

需要更精细控制（如加分块信息、返回来源、过滤元数据）时：

```python
from langchain_core.tools import tool
from langchain_chroma import Chroma

vectorstore = Chroma(...)

@tool
def search_docs(
    query: str,
    doc_type: str = "all",
) -> str:
    """搜索运维文档库。

    Args:
        query: 搜索关键词或问题
        doc_type: 文档类型过滤（manual/sop/case/all）
    """
    # 元数据过滤
    filter_dict = {"type": doc_type} if doc_type != "all" else None

    results = vectorstore.similarity_search_with_relevance_scores(
        query, k=5, filter=filter_dict,
    )

    if not results:
        return "未找到相关文档"

    # 格式化结果，包含来源和评分
    parts = []
    for doc, score in results:
        source = doc.metadata.get("source", "未知")
        parts.append(
            f"📄 [{source}] (相关度: {score:.2f})\n{doc.page_content[:500]}"
        )
    return "\n\n---\n\n".join(parts)

agent = create_deep_agent(
    model=create_llm(),
    tools=[search_docs],
    ...
)
```

### 方式三：完整的 RAG Pipeline（离线索引 + 在线检索）

适合大量文档场景，离线建索引，在线只检索：

```python
# ── 离线：文档索引（单独运行一次）──
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

def build_index(docs_dir: str, vectorstore):
    """构建文档索引（离线执行）。"""
    loader = DirectoryLoader(docs_dir, glob="**/*.md", loader_cls=TextLoader)
    docs = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
    )
    chunks = splitter.split_documents(docs)

    vectorstore.add_documents(chunks)
    print(f"已索引 {len(chunks)} 个文档块")

# ── 在线：Agent 使用 ──
@tool
def search_ops_manual(query: str) -> str:
    """搜索运维手册。当需要查找具体操作步骤、配置参数时使用。"""
    docs = vectorstore.similarity_search(query, k=3)
    return "\n---\n".join(d.page_content for d in docs)

agent = create_deep_agent(
    model=create_llm(),
    tools=[search_ops_manual],
    ...
)
```

### 三种方式对比

| 方式 | 适合场景 | 优点 | 缺点 |
|------|---------|------|------|
| `create_retriever_tool` | 快速接入 | 一行代码，LangChain 标准 | 不够灵活 |
| 自定义 `@tool` | 需要元数据过滤/格式化 | 完全可控 | 需自己写检索逻辑 |
| 完整 Pipeline | 大量文档 | 离线索引+在线检索分离 | 需要维护索引流程 |

### Autops 接入 RAG 的建议

对于 SRE/DevOps 场景，推荐：

```python
# 1. 离线构建索引（运维手册、SOP、历史故障案例）
python -m autops.index_docs --dir /data/ops-docs

# 2. Agent 配置检索工具
tools = [
    search_ops_manual,    # 搜索运维手册
    search_sop,           # 搜索 SOP 文档
    search_incident,      # 搜索历史故障案例
]

agent = create_deep_agent(
    model=create_llm(),
    tools=tools,
    system_prompt=get_main_agent_prompt(),
    backend=backend,
    checkpointer=checkpointer,
)
```

Agent 会在用户询问运维问题时**自主决定**是否调用检索工具，而不是像传统 RAG 那样每次都自动检索。

### RAG 工具 vs 传统 RAG 的体验差异

| 特性 | Deepagents RAG 工具 | 传统 RAG |
|------|-------------------|---------|
| 检索时机 | Agent 判断需要时才检索 | 每次提问都自动检索 |
| 多工具 | 可配多个检索工具（手册/SOP/案例） | 通常单一检索器 |
| 不检索时 | 直接回答（省 token、低延迟） | 仍然检索（浪费 token） |
| 结果处理 | Agent 分析后决定是否引用 | 直接拼接提示词 |
