# Learn DeepAgents

> Deepagents 框架使用经验与知识沉淀

## 目录

- [1. 核心概念](#1-核心概念)
  - [1.1 上下文、Prompt、Messages、System Message 的关系](#11-上下文promptmessagessystem-message-的关系)
  - [1.2 create_deep_agent 函数签名](#12-create_deep_agent-函数签名)
  - [1.3 自动注册的中间件](#13-自动注册的中间件)
  - [1.4 模型 Profile](#14-模型-profile)
- [2. Prompt 组装链](#2-prompt-组装链)
  - [2.1 整体流程](#21-整体流程)
  - [2.2 第一层：基础提示组装](#22-第一层基础提示组装)
  - [2.3 第二层：中间件链追加](#23-第二层中间件链追加)
  - [2.4 三种记忆在 Prompt 中的拼接方式](#24-三种记忆在-prompt-中的拼接方式)
  - [2.5 最终 Prompt 结构](#25-最终-prompt-结构)
  - [2.6 System Message 的长度控制问题](#26-system-message-的长度控制问题)
- [3. 上下文管理与压缩机制](#3-上下文管理与压缩机制)
  - [3.1 Context 会不会爆炸？](#31-context-会不会爆炸)
  - [3.2 三层压缩机制](#32-三层压缩机制)
  - [3.3 默认阈值](#33-默认阈值)
  - [3.4 手动触发压缩](#34-手动触发压缩)
- [4. 记忆体系](#4-记忆体系)
  - [4.1 总览](#41-总览)
  - [4.2 短期记忆 — Checkpointer](#42-短期记忆--checkpointer)
  - [4.3 工作记忆 — TodoList + SubAgent](#43-工作记忆--todolist--subagent)
  - [4.4 长期记忆 — AGENTS.md 文件](#44-长期记忆--agentsmd-文件)
  - [4.5 三层记忆协作](#45-三层记忆协作)
- [5. Checkpointer 持久化](#5-checkpointer-持久化)
  - [5.1 工作流程](#51-工作流程)
  - [5.2 PostgresSaver 表结构](#52-postgressaver-表结构)
  - [5.3 消息存储方式](#53-消息存储方式)
  - [5.4 会话隔离](#54-会话隔离)
- [6. Store — 跨会话共享的键值存储](#6-store--跨会话共享的键值存储)
  - [6.1 Store vs 其他记忆](#61-store-vs-其他记忆)
  - [6.2 Store 的触发机制](#62-store-的触发机制)
  - [6.3 语义搜索配置](#63-语义搜索配置)
  - [6.4 Store vs AGENTS.md 适用场景](#64-store-vs-agentsmd-适用场景)
- [7. Store 与 RAG 的区别](#7-store-与-rag-的区别)
  - [7.1 本质区别](#71-本质区别)
  - [7.2 架构对比](#72-架构对比)
  - [7.3 何时用哪个](#73-何时用哪个)
- [8. Deepagents 接入 RAG](#8-deepagents-接入-rag)
  - [8.1 核心思路](#81-核心思路)
  - [8.2 三种接入方式](#82-三种接入方式)
  - [8.3 RAG 工具 vs 传统 RAG](#83-rag-工具-vs-传统-rag)
- [9. Plan-Execute 机制](#9-plan-execute-机制)
  - [9.1 三层协作](#91-三层协作)
  - [9.2 TodoListMiddleware 详解](#92-todolistmiddleware-详解)
  - [9.3 SubAgent 委派机制](#93-subagent-委派机制)
  - [9.4 Plan-Execute 与传统 ReAct 的区别](#94-plan-execute-与传统-react-的区别)
- [10. Backend 与文件系统](#10-backend-与文件系统)
  - [10.1 LocalShellBackend 工作目录限制](#101-localshellbackend-工作目录限制)
  - [10.2 permissions 与 Shell backend 的限制](#102-permissions-与-shell-backend-的限制)
- [11. 人工审批（Human-in-the-Loop）](#11-人工审批human-in-the-loop)
- [12. LangGraph Dev 集成](#12-langgraph-dev-集成)
  - [12.1 工厂函数签名](#121-工厂函数签名)
  - [12.2 blockbuster 阻塞检测](#122-blockbuster-阻塞检测)
- [13. 可观测性与 Token 统计](#13-可观测性与-token-统计)
  - [13.1 BaseCallbackHandler 回调机制](#131-basecallbackhandler-回调机制)
  - [13.2 Token 用量来源](#132-token-用量来源)
  - [13.3 上下文窗口分项占比](#133-上下文窗口分项占比)
  - [13.4 EventSink 协议（channel 无关）](#134-eventsink-协议channel-无关)
  - [13.5 审批恢复流程的 handler](#135-审批恢复流程的-handler)

---

## 1. 核心概念

### 1.1 上下文、Prompt、Messages、System Message 的关系

| 概念 | 本质 | 通俗理解 |
|------|------|---------|
| **上下文 (Context)** | LLM 一次调用能"看到"的全部信息 | "上下文窗口" = 一次调用的全部输入 |
| **Prompt** | 发送给 LLM 的完整输入 | 上下文的实际载体，与上下文同义 |
| **Messages** | 消息列表（对话历史） | 聊天记录 |
| **System Message** | 系统级指令消息 | "你是一个 XX 助手，你的职责是..." |

**关系图**：

```
┌─────────────────────────────────────────────────────────────┐
│                    上下文 (Context) = Prompt                  │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  System Message (1 条)                                 │  │
│  │  "你是 Autops，一个 SRE/DevOps AI 运维助手..."          │  │
│  │  + BASE_AGENT_PROMPT + TodoList + Filesystem + Memory  │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Messages (N 条)                                       │  │
│  │  [HumanMessage] → [AIMessage] → [ToolMessage] → ...   │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

一句话总结：**上下文 = Prompt = System Message（你是谁） + Messages（聊了什么）**

**各角色**：

| 消息类型 | 角色 | 示例 |
|---------|------|------|
| `SystemMessage` | "你是谁、你能做什么、你应该怎么做" | "你是 Autops，一个 SRE 运维助手..." |
| `HumanMessage` | "用户说了什么" | "将 test.txt 改成 99999" |
| `AIMessage` | "Agent 之前回复了什么 / 调用了什么工具" | tool_calls=[edit_file(...)] |
| `ToolMessage` | "工具执行返回了什么结果" | "文件已修改" |

### 1.2 create_deep_agent 函数签名

```python
def create_deep_agent(
    model: str | BaseChatModel | None = None,
    tools: Sequence[BaseTool | Callable | dict[str, Any]] | None = None,
    *,
    system_prompt: str | SystemMessage | None = None,
    middleware: Sequence[AgentMiddleware] = (),
    subagents: Sequence[SubAgent | CompiledSubAgent | AsyncSubAgent] | None = None,
    skills: list[str] | None = None,
    memory: list[str] | None = None,                    # 长期记忆（AGENTS.md 文件路径）
    permissions: list[FilesystemPermission] | None = None,
    backend: BackendProtocol | BackendFactory | None = None,
    interrupt_on: dict[str, bool | InterruptOnConfig] | None = None,  # 人工审批
    response_format: ResponseFormat | type | dict | None = None,
    state_schema: type[DeepAgentState] | None = None,
    context_schema: type | None = None,
    checkpointer: Checkpointer = None,                  # 短期记忆（对话状态持久化）
    store: BaseStore | None = None,                     # 跨会话键值存储
    debug: bool = False,
    name: str | None = None,
    cache: BaseCache | None = None,
) -> CompiledStateGraph
```

**记忆相关三参数对比**：

| 参数 | 类型 | 处理方式 | 启用的功能 |
|------|------|----------|------------|
| `memory` | `list[str]`（文件路径） | 包装为 `MemoryMiddleware` | 加载 AGENTS.md 文件，注入 system prompt |
| `checkpointer` | `Checkpointer` | 原样透传给 `create_agent` | 持久化对话状态，支持多轮对话/线程恢复 |
| `store` | `BaseStore` | 原样透传给 `create_agent` | 跨线程键值存储，支持语义搜索 |

### 1.3 自动注册的中间件

`create_deep_agent` 内部自动添加：

1. **TodoListMiddleware** — 任务清单管理
2. **FilesystemMiddleware** — 文件系统工具（read/write/edit/ls/grep/glob）
3. **SubAgentMiddleware** — 子智能体委派
4. **SummarizationMiddleware** — 上下文压缩
5. **HumanInTheLoopMiddleware** — 人在回路审批（如果配置了 `interrupt_on`）
6. **PatchToolCallsMiddleware** — 工具调用修补

可通过 `middleware` 参数覆盖或 `_excluded_middleware` 排除。

### 1.4 模型 Profile

```python
model.profile  # dict or None
model.profile.get("max_input_tokens")  # 上下文窗口大小
```

有 profile 的模型（GPT-4o、Claude 等）使用 fraction 阈值；无 profile 的模型（qwen 等）使用固定 token 阈值。

可注册自定义 profile：
```python
from deepagents import register_harness_profile
```

---

## 2. Prompt 组装链

### 2.1 整体流程

```
用户 system_prompt                          ← create_deep_agent 的 system_prompt 参数
    + BASE_AGENT_PROMPT                      ← deepagents 内置基础提示
    + middleware 追加内容                    ← 各中间件逐层追加
    = 最终发送给 LLM 的 system_message
```

### 2.2 第一层：基础提示组装

`create_deep_agent` 在构建中间件栈之前，先把用户提示和内置提示拼接（graph.py:857-863）：

```python
if system_prompt is None:
    final_system_prompt = BASE_AGENT_PROMPT          # 无自定义 → 纯内置
elif isinstance(system_prompt, SystemMessage):
    final_system_prompt = SystemMessage(             # SystemMessage → 保留 blocks
        content_blocks=[*system_prompt.content_blocks,
                        {"type": "text", "text": f"\n\n{BASE_AGENT_PROMPT}"}]
    )
else:
    final_system_prompt = system_prompt + "\n\n" + BASE_AGENT_PROMPT  # 字符串 → 直接拼接
```

### 2.3 第二层：中间件链追加

所有中间件通过 `wrap_model_call` → `modify_request` 钩子，将内容**追加到 `system_message` 末尾**。

**中间件执行顺序**（graph.py:773-835）：

| 顺序 | 中间件 | 追加内容 | 记忆类型 |
|------|--------|----------|----------|
| 1 | `TodoListMiddleware` | 任务清单指令 | 工作记忆 |
| 2 | `SkillsMiddleware` | 技能列表 | 长期记忆 |
| 3 | `FilesystemMiddleware` | 文件系统工具说明 + 执行权限 | 工作记忆 |
| 4 | `SubAgentMiddleware` | 子智能体列表 + task 工具描述 | 工作记忆 |
| 5 | `SummarizationMiddleware` | 不修改 system_prompt，而是**压缩 messages** | 短期记忆 |
| 6 | `MemoryMiddleware` | `<agent_memory>` 块（AGENTS.md 内容） | 长期记忆 |

**追加方式**：`append_to_system_message`

```python
def append_to_system_message(system_message: SystemMessage | None, text: str) -> SystemMessage:
    new_content = [*system_message.content_blocks, {"type": "text", "text": f"\n\n{text}"}]
    return SystemMessage(content=new_content)
```

### 2.4 三种记忆在 Prompt 中的拼接方式

#### 短期记忆 — `messages` 列表

**载体**：`state["messages"]`，由 `SummarizationMiddleware` 管理

- 不修改 system_prompt
- 监控 `messages` 列表的 token 数量
- 当超过阈值时，用 LLM 对旧消息生成摘要，替换原始消息

#### 工作记忆 — `system_message` 追加块

**载体**：`system_message` 的追加块

- `TodoListMiddleware`：追加 `write_todos` 工具说明
- `FilesystemMiddleware`：追加文件系统工具说明
- `SubAgentMiddleware`：追加可用子智能体列表

每次 LLM 调用前，通过 `modify_request` 动态构建。

#### 长期记忆 — `<agent_memory>` 块

**载体**：`system_message` 的 `<agent_memory>` 块，由 `MemoryMiddleware` 管理

- Agent 启动时从 `backend` 下载 AGENTS.md 文件
- 文件内容存入 `state["memory_contents"]`
- 每次 LLM 调用前，通过 `modify_request` 注入 system_prompt

**注入格式**：

```
<agent_memory>
# AGENTS.md 文件内容
## 项目规范
- 代码风格: ruff, 行宽 100

## 历史经验
- nginx 502 的排查方法: ...
</agent_memory>

<memory_guidelines>
The above <agent_memory> was loaded from files in your filesystem.
You can update these files to remember new things you learn...
</memory_guidelines>
```

### 2.5 最终 Prompt 结构

```
┌─────────────────────────────────────────────────────────┐
│ system_message                                           │
│                                                          │
│ [用户自定义提示]                    ← system_prompt 参数    │
│ [BASE_AGENT_PROMPT]                ← deepagents 内置      │
│ [TodoListMiddleware]               ← 工作记忆              │
│ [FilesystemMiddleware]             ← 工作记忆              │
│ [SubAgentMiddleware]               ← 工作记忆              │
│ [MemoryMiddleware]                 ← 长期记忆              │
│   <agent_memory>...</agent_memory>                       │
│                                                          │
├─────────────────────────────────────────────────────────┤
│ messages (短期记忆)                                       │
│                                                          │
│ [摘要消息]                        ← SummarizationMiddleware │
│ [HumanMessage] / [AIMessage] / [ToolMessage] ...        │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### 2.6 System Message 的长度控制问题

**问题**：`messages` 有 `SummarizationMiddleware` 做自动压缩兜底，但 `system_message` **没有任何自动压缩机制**——只增不减。

| 组件 | 有无压缩/兜底 |
|------|--------------|
| `messages` | ✅ `SummarizationMiddleware` 自动摘要 |
| `system_message` | ❌ **无任何压缩机制** |

**组成与膨胀风险**：

```
用户提示（固定）           ~ 500 字符
BASE_AGENT_PROMPT（固定）  ~ 2000 字符
TodoList 指令（固定）      ~ 500 字符
Filesystem 指令（固定）     ~ 1000 字符
SubAgent 描述（固定）      ~ 500 字符
<agent_memory>（可变）     ← AGENTS.md 文件内容，可能很大
```

前 5 项固定可控（~5K 字符），**唯一会膨胀的是 `memory`（AGENTS.md 文件内容）**。

**缓解措施**：

1. `<memory_guidelines>` 中有指导（软约束）
2. Agent 自主裁剪（用户要求整理 AGENTS.md）
3. 人工维护（定期检查精简）
4. 自定义中间件截断（如 `MemoryTruncateMiddleware`）

---

## 3. 上下文管理与压缩机制

### 3.1 Context 会不会爆炸？

**不会。** Deepagents 默认启用 `SummarizationMiddleware`（在 `create_deep_agent` 内部自动添加），当对话 token 达到阈值时自动压缩。

### 3.2 三层压缩机制

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

**① Truncate Args**：先于摘要触发，只截断旧消息中工具调用的参数（如 `write_file` 的大段内容），保留最近的消息不动。

```python
"truncate_args_settings": {
    "trigger": ("messages", 20),   # 20 条消息时触发
    "keep": ("messages", 20),      # 保留最近 20 条不动
    "max_length": 2000,            # 参数截断到 2000 字符
    "truncation_text": "...(truncated)"
}
```

**② Summarization**：当 token 达到阈值时，用 LLM 对旧消息生成摘要，替换原始消息。

```python
{
    "trigger": ("fraction", 0.85),  # 上下文窗口的 85% 时触发
    "keep": ("fraction", 0.10),     # 保留最近 10% 的消息不动
}
```

流程：
1. 识别需要摘要的旧消息（排除 `keep` 范围内的最近消息）
2. 调用 LLM 对旧消息生成摘要
3. 将完整旧消息 offload 到 `/conversation_history/{thread_id}.md`
4. 用摘要 HumanMessage 替换旧消息
5. 摘要中嵌入 offload 文件路径，Agent 可通过 `read_file` 回溯

**③ ContextOverflowError Fallback**：如果 API 直接返回 context 超限错误，中间件会**强制摘要并重试**，而不是报错。

### 3.3 默认阈值

| 模型类型 | trigger | keep | truncate_args trigger |
|---------|---------|------|----------------------|
| 有 profile（如 GPT-4o） | `fraction 0.85` | `fraction 0.10` | `fraction 0.85` |
| 无 profile（如 qwen） | `tokens 170000` | `messages 6` | `messages 20` |

> qwen3.7-plus 没有注册 harness profile，使用固定阈值：170K token 触发摘要，保留最近 6 条消息。

### 3.4 手动触发压缩

`SummarizationToolMiddleware` 提供 `compact_conversation` 工具，Agent 可主动调用压缩：

```python
from deepagents.middleware.summarization import SummarizationToolMiddleware

agent = create_deep_agent(
    middleware=[SummarizationToolMiddleware(summ_middleware)],
)
```

---

## 4. 记忆体系

### 4.1 总览

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

### 4.2 短期记忆 — Checkpointer

- **存储**：PostgreSQL（`checkpoints` / `checkpoint_writes` 表）
- **内容**：对话消息历史（HumanMessage / AIMessage / ToolMessage）
- **生命周期**：会话级，通过 `thread_id` 隔离，进程重启不丢失
- **机制**：每次 `agent.invoke()` 自动加载历史 + 保存新状态
- **压缩**：超过阈值自动摘要（SummarizationMiddleware）

详见 [第 5 章 Checkpointer 持久化](#5-checkpointer-持久化)。

### 4.3 工作记忆 — TodoList + SubAgent

- **存储**：Agent 运行时状态（`PlanningState.todos`）
- **内容**：当前任务清单 + 子 Agent 的独立上下文
- **生命周期**：单次任务执行中，随 checkpointer 持久化
- **机制**：
  - `write_todos` 工具管理任务进度
  - `task` 工具委派子任务给 SubAgent（独立上下文窗口）
  - 子 Agent 结果以 ToolMessage 返回

详见 [第 9 章 Plan-Execute 机制](#9-plan-execute-机制)。

### 4.4 长期记忆 — AGENTS.md 文件

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

#### ⚠️ Checkpointer 缓存陷阱（重要）

`MemoryMiddleware.before_agent` 的源码逻辑：

```python
def before_agent(self, state, runtime, config):
    # Skip if already loaded
    if "memory_contents" in state:   # ← 关键判断
        return None
    # ... 从磁盘读取 AGENTS.md ...
    return MemoryStateUpdate(memory_contents=contents)
```

**问题**：开启 checkpointer 后，`state` 会从 PostgresSaver 加载。

| 场景 | 行为 | 结果 |
|---|---|---|
| 无 checkpointer | 每次 agent 创建都是新 state | 每次都重新读 AGENTS.md ✅ |
| 有 checkpointer（首次） | state 为空，读磁盘 | 正确加载 ✅ |
| 有 checkpointer（后续） | state 含旧 memory_contents | **跳过读取，用旧值** ❌ |

**后果**：
- 用户手动改 AGENTS.md → 不生效（被 checkpointer 缓存覆盖）
- Agent 用 `edit_file` 改 AGENTS.md → 也不生效（state 不更新）
- 只有清除 checkpointer 缓存才能让新内容生效

**设计原因**：为了 Anthropic prompt cache 优化。system prompt 前缀不变，cache 才能命中。但非 Anthropic 模型（qwen/OpenAI）无此需求。

#### 解决方案：AlwaysReloadMemoryMiddleware

自定义中间件，继承 `MemoryMiddleware`，重写 `before_agent` / `abefore_agent`，去掉跳过判断：

```python
class AlwaysReloadMemoryMiddleware(MemoryMiddleware):
    """每次 invoke 都重新从磁盘读取 AGENTS.md。"""

    def before_agent(self, state, runtime, config):
        # 不检查 state["memory_contents"] 是否存在
        backend = self._get_backend(state, runtime, config)
        contents = {}
        results = backend.download_files(list(self.sources))
        for path, response in zip(self.sources, results, strict=True):
            if response.error == "file_not_found":
                continue
            if response.content is not None:
                contents[path] = response.content.decode("utf-8")
        return MemoryStateUpdate(memory_contents=contents)
```

使用方式：通过 `middleware=` 参数传入（而非 `memory=`）：

```python
from autops.middleware import AlwaysReloadMemoryMiddleware

agent = create_deep_agent(
    model="...",
    # memory=["/memory/AGENTS.md"],  # ❌ 不用，会触发官方 MemoryMiddleware 的缓存逻辑
    middleware=[
        AlwaysReloadMemoryMiddleware(
            backend=backend,
            sources=["/memory/AGENTS.md"],
        ),
    ],
)
```

**代价**：system prompt 内容随 AGENTS.md 变化，prompt cache 失效。对非 Anthropic 模型无影响。

#### 记忆更新

Agent 通过 `edit_file` 工具**自主更新**记忆文件：

```
用户: "记住我的服务器 IP 是 192.168.1.100"
    ↓
Agent 调用 edit_file 修改 AGENTS.md
    追加: "用户服务器 IP: 192.168.1.100"
    ↓
下次会话 AlwaysReloadMemoryMiddleware 重新加载 AGENTS.md
    → Agent 知道服务器 IP 了
```

> **注意**：若使用官方 `MemoryMiddleware`，Agent 修改 AGENTS.md 后**不会立即生效**（checkpointer 缓存旧 state）。必须用 `AlwaysReloadMemoryMiddleware` 才能让 Agent 的修改下次 invoke 立即生效。

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

### 4.5 三层记忆协作

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

---

## 5. Checkpointer 持久化

### 5.1 工作流程

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

### 5.2 PostgresSaver 表结构

| 表 | 作用 |
|---|------|
| `checkpoints` | 检查点主表，存储状态快照（JSONB）+ 元数据 |
| `checkpoint_blobs` | 大对象存储（msgpack 编码的消息内容） |
| `checkpoint_writes` | 写入操作日志（每步 LLM/工具调用的中间写入） |
| `checkpoint_migrations` | 迁移版本记录 |

### 5.3 消息存储方式

- `checkpoints.checkpoint` (JSONB)：只存版本号引用，不存消息明文
- `checkpoint_writes.blob` (bytea)：存 msgpack 编码的消息内容
- 解码用 `JsonPlusSerializer.loads_typed((type, blob))`

### 5.4 会话隔离

通过 `thread_id` 区分会话（飞书场景：`chat_id + user_id`），不同会话的 checkpoint 互不干扰。

---

## 6. Store — 跨会话共享的键值存储

`store` 参数不是第四层记忆，而是 **LangGraph 的 BaseStore**，一种**跨会话共享的持久化键值存储**。

### 6.1 Store vs 其他记忆

| 组件 | 存储类型 | 作用域 | 特点 |
|------|---------|--------|------|
| checkpointer | 对话状态 | 单会话 (thread_id) | 自动加载/保存消息历史 |
| AGENTS.md (memory) | 系统提示词 | 全局 | 始终注入到每次 LLM 调用 |
| **store** | **键值对 (key-value)** | **跨会话共享** | **按 namespace 隔离，支持语义搜索** |

Store 提供 API：
- `put(namespace, key, value)` — 存储数据
- `get(namespace, key)` — 读取数据
- `search(namespace, query)` — 语义搜索（需要配置 index）
- `delete(namespace, key)` — 删除数据
- `list_namespaces()` — 列出命名空间

### 6.2 Store 的触发机制

**Store 没有自动触发机制**。与 checkpointer（自动加载/保存）和 memory（自动注入提示词）不同，Store 的读写完全由**自定义工具**驱动。

| 记忆类型 | 触发方式 | 自动/手动 |
|---------|---------|----------|
| checkpointer | `agent.invoke()` 时自动加载/保存 | **自动** |
| memory (AGENTS.md) | `MemoryMiddleware` 启动时自动加载，注入提示词 | **自动** |
| **store** | **Agent 调用带 `InjectedStore` 的自定义工具** | **手动（工具驱动）** |

需要自定义工具，通过 `InjectedStore` 注入 store 实例：

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
```

`InjectedStore()` 注入对 LLM 不可见（LLM 只看到 `key` 和 `content` 参数）。

### 6.3 语义搜索配置

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
```

### 6.4 Store vs AGENTS.md 适用场景

| 特性 | AGENTS.md (memory) | Store |
|------|-------------------|-------|
| 数据格式 | Markdown 文本 | 任意 JSON/键值对 |
| 加载方式 | 全量注入系统提示词 | 按需读取（Agent 用工具查询） |
| 语义搜索 | 不支持 | 支持（配置 index） |
| 更新方式 | edit_file 修改文件 | put/delete API |
| 占用 token | 始终占用（在提示词中） | 按需加载（不占提示词） |

| 场景 | 推荐方案 | 原因 |
|------|---------|------|
| 项目编码规范 | AGENTS.md | 始终在提示词中，每次都生效 |
| 用户个人偏好 | AGENTS.md | 量少，始终需要 |
| 运维知识库（100+ 条目） | Store | 量大，按需查询不占 token |
| 多用户共享数据 | Store | 按 namespace 隔离 |
| 历史故障分析记录 | Store | 需要语义搜索 |
| 跨会话任务协作 | Store | 不同 thread 共享数据 |

---

## 7. Store 与 RAG 的区别

Store 配置了 `index` 后确实支持向量语义搜索，看起来像 RAG，但两者定位和架构不同。

### 7.1 本质区别

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

### 7.2 架构对比

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

### 7.3 何时用哪个

| 场景 | 推荐 | 原因 |
|------|------|------|
| 搜索 1000 页运维手册 | RAG | 非结构化文档，需分块+自动检索 |
| Agent 积累的故障处理经验 | Store | 结构化数据，Agent 自主管理 |
| 用户上传 PDF 提问 | RAG | 文档检索场景 |
| 多 Agent 共享运维知识 | Store | 跨会话共享，按需查询 |
| 代码库智能问答 | RAG | 大量代码文件，需自动检索 |
| Agent 记住用户服务器配置 | Store | 少量结构化数据 |

可以结合使用：Store 是 Agent 的"记忆本"，Agent 自主读写；RAG 是"搜索引擎"，自动检索外部文档。两者互补。

---

## 8. Deepagents 接入 RAG

Deepagents 框架**没有内置 RAG 模块**。接入 RAG 的方式是**自定义检索工具**，Agent 通过 tool calling 按需检索。

### 8.1 核心思路

RAG 在 Deepagents 中就是一个普通工具：

```
用户提问 → LLM 判断需要检索 → 调用 rag_search 工具 → 返回文档片段 → LLM 生成回答
```

### 8.2 三种接入方式

**方式一：LangChain Retriever 工具（最简单）**

```python
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain.tools.retriever import create_retriever_tool

embeddings = OpenAIEmbeddings(model="text-embedding-3-small", ...)
vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings, ...)

retriever_tool = create_retriever_tool(
    retriever=vectorstore.as_retriever(search_kwargs={"k": 5}),
    name="search_ops_docs",
    description="搜索运维知识库...",
)

agent = create_deep_agent(model=..., tools=[retriever_tool], ...)
```

**方式二：自定义 RAG 工具（更灵活）**

```python
@tool
def search_docs(query: str, doc_type: str = "all") -> str:
    """搜索运维文档库。"""
    results = vectorstore.similarity_search_with_relevance_scores(query, k=5, filter=...)
    return formatted_results
```

**方式三：完整的 RAG Pipeline（离线索引 + 在线检索）**

```python
# 离线建索引
def build_index(docs_dir, vectorstore):
    loader = DirectoryLoader(docs_dir, glob="**/*.md", loader_cls=TextLoader)
    chunks = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50).split_documents(loader.load())
    vectorstore.add_documents(chunks)

# 在线检索
@tool
def search_ops_manual(query: str) -> str:
    """搜索运维手册。"""
    return "\n---\n".join(d.page_content for d in vectorstore.similarity_search(query, k=3))
```

| 方式 | 适合场景 | 优点 | 缺点 |
|------|---------|------|------|
| `create_retriever_tool` | 快速接入 | 一行代码，LangChain 标准 | 不够灵活 |
| 自定义 `@tool` | 需要元数据过滤/格式化 | 完全可控 | 需自己写检索逻辑 |
| 完整 Pipeline | 大量文档 | 离线索引+在线检索分离 | 需要维护索引流程 |

### 8.3 RAG 工具 vs 传统 RAG

| 特性 | Deepagents RAG 工具 | 传统 RAG |
|------|-------------------|---------|
| 检索时机 | Agent 判断需要时才检索 | 每次提问都自动检索 |
| 多工具 | 可配多个检索工具（手册/SOP/案例） | 通常单一检索器 |
| 不检索时 | 直接回答（省 token、低延迟） | 仍然检索（浪费 token） |
| 结果处理 | Agent 分析后决定是否引用 | 直接拼接提示词 |

---

## 9. Plan-Execute 机制

Deepagents 的 plan-execute 不是独立的规划器+执行器架构，而是通过 **TodoListMiddleware + 系统提示词 + SubAgent** 三者协作实现。

### 9.1 三层协作

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

### 9.2 TodoListMiddleware 详解

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

**write_todos 工具行为**：每次调用**替换整个列表**，不是增量更新。

**何时规划**：
- ≥3 个步骤的复杂任务 → 使用 write_todos
- <3 步的简单任务 → 直接执行，不用 write_todos
- 用户明确要求规划时 → 使用 write_todos

### 9.3 SubAgent 委派机制

主 Agent 通过 `task` 工具委派子任务：

```python
from deepagents import SubAgent

subagents = [
    SubAgent(
        name="log_analyzer",
        description="分析日志文件",
        system_prompt="你是一个日志分析专家...",
        tools=[read_file, grep],
        # model="openai:gpt-4o-mini",  # 可用不同模型
    ),
]

agent = create_deep_agent(model="...", subagents=subagents)
```

**子 Agent 特点**：
- **独立上下文窗口**：不消耗主 Agent 的 token 配额
- **独立工具集**：可以限制子 Agent 的能力
- **独立模型**：可以用更便宜的模型执行子任务
- **结果返回**：子 Agent 执行完后，结果以 ToolMessage 返回给主 Agent

### 9.4 Plan-Execute 与传统 ReAct 的区别

| 特性 | 传统 ReAct | Deepagents Plan-Execute |
|------|-----------|------------------------|
| 规划 | 无显式规划，逐步反应 | LLM 自主决定是否用 write_todos 规划 |
| 状态追踪 | 无 | todos 列表持久化到 checkpointer |
| 任务委派 | 不支持 | SubAgent 独立上下文执行子任务 |
| 复杂任务 | 容易迷失方向 | todo 列表 + 子 Agent 避免上下文爆炸 |
| 简单任务 | 直接执行 | 也直接执行（不强制规划） |

**关键设计**：规划是**可选的**。LLM 根据任务复杂度自主决定是否调用 `write_todos`，简单任务直接执行不浪费 token。

---

## 10. Backend 与文件系统

### 10.1 LocalShellBackend 工作目录限制

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

#### ⚠️ virtual_mode 路径规则（重要）

`virtual_mode=True` 时，**所有路径都被解释为相对于 root_dir 的虚拟绝对路径**：

| 传入路径 | 实际查找位置 | 能否找到 |
|---|---|---|
| `"/memory/AGENTS.md"` | `root_dir/memory/AGENTS.md` | ✅ |
| `"memory/AGENTS.md"` | `root_dir/memory/AGENTS.md` | ✅（相对路径也行） |
| `"/opt/Autops/workspace/memory/AGENTS.md"` | `root_dir/opt/Autops/workspace/memory/AGENTS.md` | ❌ 真实绝对路径找不到 |

**关键结论**：传给 `MemoryMiddleware` 的 `sources` 路径**必须用虚拟绝对路径**（以 `/` 开头），不能用真实绝对路径。

```python
# ❌ 错误：用真实绝对路径，virtual_mode 下找不到
memory=["/opt/Autops/workspace/memory/AGENTS.md"]

# ✅ 正确：虚拟绝对路径
memory=["/memory/AGENTS.md"]
```

验证方式：
```python
backend = LocalShellBackend(root_dir="/opt/Autops/workspace", virtual_mode=True)
result = backend.download_files(["/memory/AGENTS.md"])
# result[0].content 是文件内容（bytes）
# result[0].error 是 None 或 "file_not_found"
```

### 10.2 permissions 与 Shell backend 的限制

`FilesystemPermission` **不支持**带 Shell 执行的 backend（`LocalShellBackend`）：

```
NotImplementedError: FilesystemMiddleware does not yet support permissions
with backends that provide command execution
```

只能用 `virtual_mode` 限制文件路径，不能用 `permissions` 做细粒度控制。

---

## 11. 人工审批（Human-in-the-Loop）

通过 `interrupt_on` 参数配置：

```python
agent = create_deep_agent(
    ...,
    interrupt_on={
        "edit_file": True,
        "execute": True,
    },
)
```

**工作流程**：

1. Agent 调用被配置的工具（如 `edit_file`）
2. `HumanInTheLoopMiddleware.after_model` 检测到工具调用匹配 `interrupt_on`
3. 构造 `HITLRequest`（含 `action_requests` 和 `review_configs`）
4. 调用 `interrupt(hitl_request)` 暂停图执行
5. 等待 `Command(resume={"decisions": [...]})` 恢复

**Decision 类型**：

| 类型 | 说明 | 格式 |
|------|------|------|
| `approve` | 批准执行原始参数 | `{"type": "approve"}` |
| `edit` | 修改参数后执行 | `{"type": "edit", "edited_action": {...}}` |
| `reject` | 拒绝，反馈给 Agent | `{"type": "reject", "message": "..."}` |
| `respond` | 直接返回结果，跳过工具 | `{"type": "respond", "value": "..."}` |

**Resume 格式**：

```python
agent.invoke(
    Command(resume={"decisions": [{"type": "approve"}]}),
    config={"thread_id": thread_id},
)
```

**注意**：`interrupt_on` **依赖 `checkpointer`**——暂停状态需要持久化。

---

## 12. LangGraph Dev 集成

### 12.1 工厂函数签名

LangGraph dev 的 `invoke_factory` 根据参数数量分类工厂函数：

| 参数数 | 分类 | 行为 |
|--------|------|------|
| 0 | 无参 | `value()` 无参调用 ✓ |
| 1 | config 或 runtime | `value(param=config_dict)` 注入参数 |
| 2 | config + runtime | 按类型注解决定参数含义 |

**关键**：工厂函数必须**无参数**，否则 LangGraph dev 会把 `config` dict 当作第一个参数传入。

```python
# ❌ 错误：有参数，LangGraph dev 会注入 config
def create_main_agent(tools: list | None = None) -> CompiledStateGraph: ...

# ❌ 错误：可选参数也不行，LangGraph dev 会把 config dict 注入到 user_id
def create_main_agent(user_id: str | None = None) -> CompiledStateGraph: ...
# 调用时 user_id 实际值：{'configurable': {'thread_id': 'xxx'}}
# → 后续 user_id / path 会报 TypeError

# ❌ 错误：用 **kwargs 吞参数 + isinstance 防御也不彻底
def create_main_agent(user_id: str | None = None, **_kwargs: object) -> CompiledStateGraph: ...
# 虽然 isinstance 检查能挡住 dict，但语义不清晰

# ✅ 正确：工厂函数完全无参数，内部逻辑拆到带参数的内部函数
def _build_agent(user_id: str | None = None) -> CompiledStateGraph:
    """带参数的内部函数，channels 直接调用。"""
    return create_deep_agent(...)

def create_main_agent() -> CompiledStateGraph:
    """LangGraph dev 工厂入口，无参数。"""
    return _build_agent(user_id=None)
```

**channels 调用方式**：
- LangGraph dev：`langgraph.json` 指向 `create_main_agent`（无参）
- 飞书 channel：`from autops.agents.main_agent import _build_agent; agent = _build_agent(user_id=user_id)`
- CLI channel：`create_main_agent()`（无参，单用户场景）

### 12.2 blockbuster 阻塞检测

LangGraph dev 用 `blockbuster` 检测事件循环中的同步阻塞调用（`os.mkdir`、`open` 等）。

**规则**：
- 模块导入在**线程池**中执行 → blockbuster 不拦截
- 工厂函数在**事件循环**中执行 → blockbuster 拦截阻塞 I/O

**解决方案**：将阻塞 I/O（如 `os.mkdir`）移到模块级别：

```python
# 模块级别（线程池，安全）
_WORKSPACE = _resolve_workspace()
_WORKSPACE.mkdir(parents=True, exist_ok=True)

def create_main_agent() -> CompiledStateGraph:
    # 事件循环中调用，不能有阻塞 I/O
    return create_deep_agent(...)
```

---

## 13. 可观测性与 Token 统计

### 13.1 BaseCallbackHandler 回调机制

LangChain 提供 `BaseCallbackHandler`，注册后可在 LLM/工具/链路的关键节点收到回调：

| 回调 | 触发时机 | 典型用途 |
|---|---|---|
| `on_chat_model_start` | LLM 调用前 | 记录 messages、提取 system/tools |
| `on_llm_end` | LLM 响应后 | 提取 token usage（prompt/completion tokens） |
| `on_tool_start` / `on_tool_end` | 工具执行前后 | 实时通知、耗时统计 |
| `on_chain_error` | 链路错误 | 区分 Interrupt（正常）和真实错误 |

注册方式：
```python
agent.invoke(
    {"messages": [user_msg]},
    config={
        "thread_id": thread_id,
        "callbacks": [handler],
    },
)
```

### 13.2 Token 用量来源

LLM 调用结束后的 token 用量有两个来源：

1. **`response.llm_output["token_usage"]`**（OpenAI 风格）
   ```python
   usage = llm_output.get("token_usage") or {}
   prompt_t = usage.get("prompt_tokens", 0)
   completion_t = usage.get("completion_tokens", 0)
   ```

2. **`AIMessage.usage_metadata`**（LangChain 标准，更通用）
   ```python
   um = last_msg.usage_metadata
   prompt_t = um.get("input_tokens", 0)
   completion_t = um.get("output_tokens", 0)
   ```

**注意**：两者有时只返回一个。优先用 `llm_output`，为 0 时回退到 `usage_metadata`。

### 13.3 上下文窗口分项占比

通过 tiktoken 本地估算 system/tools/messages 的 token 数，计算占比：

```python
# 总量以 API 实测为准（最准确）
total = last_input_tokens  # API 返回的 prompt_tokens

# 分项用 tiktoken 估算
system_tokens = count_tokens(system_text)
tools_tokens = count_tokens(tools_schema_text)
messages_tokens = sum(count_tokens(extract_text(m)) for m in messages)

# 其他开销 = 总量 - 三项已知（吸收 tokenizer 偏差）
other_tokens = max(0, total - system_tokens - tools_tokens - messages_tokens)
```

**设计要点**：
- 总量用 API 实测（最准），不追求分项之和等于总量
- 分项用 tiktoken 本地估算（有偏差，但能看分布）
- "其他开销"吸收 tokenizer 偏差 + 结构标记开销
- 分项之和永远等于 API 实测总量

### 13.4 EventSink 协议（channel 无关）

可观测性 handler 应该与具体 channel 解耦。通过 `EventSink` 协议让各 channel 自行实现通知方式：

```python
class EventSink(Protocol):
    def notify_tool_start(self, turn: int, tool_name: str, params: str) -> None: ...
    def notify_tool_end(self, turn: int, tool_name: str, output: str, elapsed: float) -> None: ...
    def notify_tool_error(self, turn: int, tool_name: str, error: str, elapsed: float) -> None: ...
    def notify_summary(self, summary: str) -> None: ...
```

各 channel 实现自己的 sink：
- **飞书**：`FeishuEventSink`（包装 `FeishuReporter`，发消息到飞书）
- **CLI**：`CliEventSink`（用 rich 打印到终端）
- **API**：可自定义 sink 返回 JSON

使用方式：
```python
handler = AgentObservabilityHandler(sink=FeishuEventSink(reporter))
agent.invoke(..., config={"callbacks": [handler]})
# 结束后
handler.summary()  # 内部会自动调用 sink.notify_summary
```

### 13.5 审批恢复流程的 handler

`interrupt_on` 触发后，Agent 暂停。用户点击批准后，用 `Command(resume=...)` 恢复执行：

```python
# 第一次 invoke（触发 interrupt）
handler1 = AgentObservabilityHandler(sink=sink)
result = agent.invoke({"messages": [msg]}, config={"callbacks": [handler1], ...})
# result 包含 __interrupt__，summary 在这里不会被调用

# 审批后恢复（新的 LLM 调用，需要新的 handler）
handler2 = AgentObservabilityHandler(sink=sink)
result = agent.invoke(
    Command(resume={"decisions": [{"type": "approve"}]}),
    config={"callbacks": [handler2], ...},
)
handler2.summary()  # 恢复执行后的统计
```

**关键**：恢复执行是新一轮 LLM 调用，token 应单独统计（不与中断前混淆）。
