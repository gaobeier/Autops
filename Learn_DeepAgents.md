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
  - [4.6 基于 Store 的三种长期记忆类型](#46-基于-store-的三种长期记忆类型)
- [5. Checkpointer 持久化](#5-checkpointer-持久化)
  - [5.1 工作流程](#51-工作流程)
  - [5.2 PostgresSaver 表结构](#52-postgressaver-表结构)
  - [5.3 State 的 channel 详解](#53-state-的-channel-详解)
  - [5.4 memory_contents 与 AGENTS.md 的关系](#54-memory_contents-与-agentsmd-的关系)
  - [5.5 如何直接读取 state](#55-如何直接读取-state)
  - [5.6 会话隔离](#56-会话隔离)
- [6. Store — 跨会话共享的键值存储](#6-store--跨会话共享的键值存储)
  - [6.1 Store vs 其他记忆](#61-store-vs-其他记忆)
  - [6.2 Store 的触发机制](#62-store-的触发机制)
  - [6.3 语义搜索配置](#63-语义搜索配置)
  - [6.4 Store vs AGENTS.md 适用场景](#64-store-vs-agentsmd-适用场景)
  - [6.5 Store 完整使用示例](#65-store-完整使用示例)
  - [6.6 什么数据应该存到 Store](#66-什么数据应该存到-store)
  - [6.7 Store 的 Namespace 设计](#67-store-的-namespace-设计)
  - [6.8 Autops 中的 Store 使用建议](#68-autops-中的-store-使用建议)
  - [6.9 向量数据库与 Embedding 模型](#69-向量数据库与-embedding-模型)
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
  - [10.3 LocalShellBackend 的安全限制（重要）](#103-localshellbackend-的安全限制重要)
  - [10.4 bwrap（bubblewrap）沙箱方案](#104-bwrapbubblewrap-沙箱方案)
- [11. 人工审批（Human-in-the-Loop）](#11-人工审批human-in-the-loop)
  - [11.1 基本用法](#111-基本用法)
  - [11.2 InterruptOnConfig + when 谓词（动态审批）](#112-interruptonconfig--when-谓词动态审批)
  - [11.3 三级安全策略](#113-三级安全策略)
  - [11.4 工作流程](#114-工作流程)
- [12. LangGraph Dev 集成](#12-langgraph-dev-集成)
  - [12.1 工厂函数签名](#121-工厂函数签名)
  - [12.2 blockbuster 阻塞检测](#122-blockbuster-阻塞检测)
- [13. 可观测性与 Token 统计](#13-可观测性与-token-统计)
  - [13.1 BaseCallbackHandler 回调机制](#131-basecallbackhandler-回调机制)
  - [13.2 Token 用量来源](#132-token-用量来源)
  - [13.3 上下文窗口分项占比](#133-上下文窗口分项占比)
  - [13.4 EventSink 协议（channel 无关）](#134-eventsink-协议channel-无关)
  - [13.5 审批恢复流程的 handler](#135-审批恢复流程的-handler)
- [14. Store 落地实践（Autops 三种长期记忆）](#14-store-落地实践autops-三种长期记忆)
  - [14.1 工具与 namespace 实际设计](#141-工具与-namespace-实际设计)
  - [14.2 value 结构与向量索引字段](#142-value-结构与向量索引字段)
  - [14.3 JSON 字符串参数兼容（list 转 str）](#143-json-字符串参数兼容list-转-str)
  - [14.4 PostgresStore 初始化的正确姿势](#144-postgresstore-初始化的正确姿势)
  - [14.5 OpenAI 兼容 Embedding 封装](#145-openai-兼容-embedding-封装)
  - [14.6 InjectedStore + infer_schema=False 的坑](#146-injectedstore--infer_schemafalse-的坑)
- [15. 路径方案演进与 workspace 隔离](#15-路径方案演进与-workspace-隔离)
  - [15.1 virtual_mode 的路径规则](#151-virtual_mode-的路径规则)
  - [15.2 从绝对路径到相对路径的提示词规范](#152-从绝对路径到相对路径的提示词规范)
  - [15.3 workspace 隔离设计](#153-workspace-隔离设计)
- [16. 飞书 Channel 集成实践](#16-飞书-channel-集成实践)
  - [16.1 EventSink 的飞书实现](#161-eventsink-的飞书实现)
  - [16.2 审批恢复流程与 handler 重建](#162-审批恢复流程与-handler-重建)
  - [16.3 群聊与私聊的会话隔离](#163-群聊与私聊的会话隔离)

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

### 4.6 基于 Store 的三种长期记忆类型

当 Agent 需要管理大量跨会话数据时，AGENTS.md（全量注入 system prompt）不再适合。
此时可使用 Store（按需查询）实现更精细的长期记忆分类。

参考认知科学的记忆分类，长期记忆可分为三种类型：

```
长期记忆 (Store)
├── 情景记忆 (Episodic) — 存事件
│   "上次修 auth.py 的空指针 bug 是怎么修的？"
│
├── 语义记忆 (Semantic) — 存知识
│   "这个项目用什么数据库？"
│
└── 程序记忆 (Procedural) — 存操作模式
    "处理退款的步骤是什么？"
```

#### 情景记忆（Episodic）— 存事件

**存什么**：具体的交互事件，有明确的时间戳

```json
{
    "type": "episodic",
    "timestamp": "2026-04-25T14:30:00",
    "session_id": "sess_abc123",
    "event": "修复了 auth.py 的空指针异常",
    "context": "用户报告登录页面 500 错误",
    "outcome": "成功，pytest 全部通过",
    "files": ["auth.py"],
    "tags": ["bugfix", "auth"]
}
```

**存储位置**：PG 结构化字段（时间/标签精确查询）+ pgvector（event 文本 embedding 语义搜索）

**Namespace 设计**：`("episodic", user_id)`

**检索策略**：时间优先 + 语义辅助
- "上次修 auth 的 bug" → 先按 tag="auth" 精确过滤 + ORDER BY timestamp DESC → 再用向量排序找最相关的那次

**关键特征**：有明确时间戳，按时间线组织，检索时涉及"上次""昨天""最近"等时间条件

#### 语义记忆（Semantic）— 存知识

**存什么**：事实性知识，相对稳定，不绑定具体时间

```json
{
    "type": "semantic",
    "category": "project_config",
    "key": "tech_stack",
    "value": "Python 3.12, FastAPI, PostgreSQL, pytest",
    "confidence": 0.95,
    "last_verified": "2026-04-27"
}
```

**存储位置**：PG Key-Value 为主（结构化事实，精确匹配）+ pgvector 为辅（模糊查询）

**Namespace 设计**：`("semantic", category)`（全局共享，不按用户隔离）

**检索策略**：精确匹配优先，语义搜索兜底
- "用什么数据库？" → WHERE category="project_config" AND key LIKE "%database%" → 直接命中
- "有什么和数据持久化相关的？" → 向量检索 embedding("数据持久化") → 找到 tech_stack 和 db_config

**关键特征**：相对稳定，需要定期验证是否过时（项目可能升级了技术栈）

#### 程序记忆（Procedural）— 存操作模式

**存什么**：从多次成功执行中抽象出的可复用"剧本"

```json
{
    "type": "procedural",
    "trigger": "用户要求处理退款",
    "steps": [
        "查询订单状态 → 确认订单存在且已完成",
        "检查退款政策 → 是否在退款期限内",
        "调用退款 API → 发起退款",
        "发送通知 → 邮件+站内信"
    ],
    "success_rate": 0.92,
    "learned_from": ["session_001", "session_015", "session_023"]
}
```

**存储位置**：PG（结构化步骤序列）+ pgvector（trigger 描述 embedding，场景匹配）

**Namespace 设计**：`("procedural",)`（全局共享，不按用户隔离）

**检索策略**：场景匹配
- 用户说"帮我退款" → 向量检索 embedding("帮我退款") 与所有 trigger 比较 → 命中"用户要求处理退款" → Agent 按 steps 执行

**关键特征**：从多次成功经验中抽象出来的"最佳实践"，检索时靠场景匹配

#### 三种记忆对比

| 维度 | 情景记忆 | 语义记忆 | 程序记忆 |
|---|---|---|---|
| **存什么** | 事件（有时间的经历） | 知识（事实/配置） | 操作模式（步骤序列） |
| **数据结构** | event + timestamp + tags | category + key + value | trigger + steps + success_rate |
| **检索方式** | 时间优先 + 语义辅助 | 精确匹配优先 + 语义兜底 | 场景匹配（trigger 向量相似度） |
| **时效性** | 按时间线，旧的较少用 | 需定期验证是否过时 | 按 success_rate 排序 |
| **是否需要向量** | ✅ 需要（"类似的 bug"语义匹配） | ⚠️ 可选（精确查询为主，偶尔模糊） | ✅ 必须（trigger 场景匹配） |
| **是否按用户隔离** | ✅ 是（个人事件） | ❌ 否（客观事实，全局共享） | ❌ 否（通用最佳实践，全局共享） |
| **Autops 场景** | "上次服务器磁盘满了怎么处理的" | "航信项目用什么网段" | "Docker 容器排障的标准步骤" |
| **Namespace** | `("episodic", user_id)` | `("semantic", category)` | `("procedural",)` |

#### 三种记忆与 AGENTS.md 的关系

```
AGENTS.md（始终注入，少量高频）
    - 核心用户偏好
    - 项目编码规范
    - 常用配置
    ↓ 量大时不够用

Store 三种长期记忆（按需查询，大量低频）
    ├── episodic: 历史事件记录（按时间/标签检索）
    ├── semantic: 事实知识库（精确 + 语义搜索）
    └── procedural: 操作剧本库（场景匹配触发）
```

**选择原则**：
- **少量 + 每次都需要** → AGENTS.md
- **大量 + 按需查询** → Store
- **有时间属性的事件** → 情景记忆（episodic）
- **稳定的事实/配置** → 语义记忆（semantic）
- **可复用的操作步骤** → 程序记忆（procedural）

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
| `checkpoints` | 检查点主表，存储 checkpoint 元数据 + 结构引用（JSONB） |
| `checkpoint_blobs` | **实际 state 数据**，按 channel 分表存储（msgpack 二进制） |
| `checkpoint_writes` | 写入操作日志（每步 LLM/工具调用的中间写入） |
| `checkpoint_migrations` | 迁移版本记录 |

#### State 的分 channel 存储机制

State **不是存在 `checkpoints` 表的一个字段里**，而是按 channel 拆分存在 `checkpoint_blobs` 表：

```
checkpoints 表（元数据）
    ├── thread_id
    ├── checkpoint_id
    ├── checkpoint (jsonb)    ← 结构引用（指向各 channel 的 version），不是 state 本身
    └── metadata (jsonb)      ← 来源、step 等元信息

checkpoint_blobs 表（实际 state 数据）
    ├── channel=messages        ← 对话消息（60KB~95KB）
    ├── channel=todos           ← 任务列表（130B~135B）
    ├── channel=memory_contents ← 长期记忆缓存（304B~324B）
    ├── channel=__pregel_tasks  ← LangGraph 内部任务调度
    └── blob (bytea)            ← msgpack 序列化的二进制
```

**关键点**：`checkpoints.checkpoint` 字段只存结构引用（哪些 channel 的哪个 version），不存 state 明文。

### 5.3 State 的 channel 详解

每个 channel 对应 AgentState 的一个字段：

| channel | 对应 state 字段 | 内容 | 大小 | 来源 |
|---|---|---|---|---|
| `messages` | `state["messages"]` | 对话消息历史（HumanMessage/AIMessage/ToolMessage） | 60KB~95KB | 每次 LLM/工具调用自动追加 |
| `todos` | `state["todos"]` | 任务列表（`write_todos` 工具写入） | 130B~135B | Agent 调用 `write_todos` 时更新 |
| `memory_contents` | `state["memory_contents"]` | AGENTS.md 文件内容的**缓存副本** | 304B~324B | `MemoryMiddleware.before_agent` 加载 |
| `__pregel_tasks` | LangGraph 内部 | 任务调度状态 | 1B~132B | 框架自动管理 |

### 5.4 memory_contents 与 AGENTS.md 的关系

`memory_contents` 是 **AGENTS.md 文件内容在 state 中的缓存副本**，两者关系：

```
AGENTS.md（磁盘文件，源头）
    - Agent 通过 edit_file 写入
    - 永久存储，跨进程重启不丢失
    - 用户可直接编辑
        ↓
    AlwaysReloadMemoryMiddleware.before_agent()
    （每次 invoke 重新读磁盘）
        ↓
memory_contents（state 中的缓存副本）
    - dict: {文件路径: 文件内容}
    - 随 checkpoint 持久化到 PG
    - 用于 modify_request 时取内容注入 system prompt
        ↓
    MemoryMiddleware.modify_request()
    （每次 LLM 调用时）
        ↓
system prompt 的 <agent_memory> 块
    - 最终注入到 LLM 看到的 system prompt
    - LLM 根据记忆内容回答问题
```

**为什么要在 state 里存一份副本？**

官方 `MemoryMiddleware` 的设计是为了 prompt cache 优化：
1. 首次加载 AGENTS.md → 存入 state
2. 后续 invoke 从 state 取（不重新读磁盘）
3. system prompt 内容不变 → Anthropic prompt cache 命中

使用 `AlwaysReloadMemoryMiddleware` 后，state 里的 `memory_contents` 只是**过路缓存**，真正的源头是磁盘上的 AGENTS.md。

### 5.5 如何直接读取 state

```python
from langgraph.checkpoint.postgres import PostgresSaver

saver = PostgresSaver(conn)
checkpoint = saver.get({"configurable": {"thread_id": thread_id}})
state = checkpoint["channel_values"]

# 查看 todos
todos = state.get("todos", [])
# [{'content': '编写 HTTP 服务器代码', 'status': 'completed'},
#  {'content': '测试 HTTP 服务器', 'status': 'in_progress'}]

# 查看 memory_contents
memory = state.get("memory_contents", {})
# {'/memory/AGENTS.md': '# Autops 长期记忆\n...'}

# 查看 messages（对话历史）
messages = state.get("messages", [])
```

### 5.6 会话隔离

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

### 6.5 Store 完整使用示例

#### 初始化 Store

```python
from langgraph.store.memory import InMemoryStore  # 开发用
# 或
from langgraph.store.postgres import PostgresStore  # 生产用

# 方式 1：内存 Store（开发调试）
store = InMemoryStore()

# 方式 2：Postgres Store（生产，带语义搜索）
store = PostgresStore.from_conn_string(
    conn_string="postgresql://autops:xxx@host:5432/autops",
    index={
        "dims": 1536,
        "fields": ["content"],
        "embed": "openai:text-embedding-3-small",
    },
)
```

#### 传入 create_deep_agent

```python
agent = create_deep_agent(
    model=create_llm(),
    tools=[internet_search, save_knowledge, search_knowledge],
    backend=backend,
    checkpointer=checkpointer,
    store=store,  # ← 传入 store
)
```

#### 自定义工具（Agent 通过工具读写 Store）

```python
from typing import Annotated
from langgraph.prebuilt import InjectedStore
from langgraph.store.base import BaseStore
from langchain_core.tools import tool

@tool
def save_knowledge(
    key: str,
    content: str,
    category: str = "general",
    store: Annotated[BaseStore, InjectedStore()],
) -> str:
    """保存运维知识到知识库。

    Args:
        key: 知识条目的唯一标识（如 "nginx-memory-tuning"）
        content: 知识内容（Markdown 格式）
        category: 分类（如 "nginx"、"docker"、"network"）
    """
    store.put(
        namespace=("ops_knowledge", category),
        key=key,
        value={"content": content, "category": category},
    )
    return f"已保存知识: {key}（分类: {category}）"

@tool
def search_knowledge(
    query: str,
    category: str = "",
    store: Annotated[BaseStore, InjectedStore()],
) -> str:
    """搜索运维知识库。

    Args:
        query: 搜索关键词或自然语言查询
        category: 限定分类（为空则搜索全部分类）
    """
    if category:
        ns = ("ops_knowledge", category)
    else:
        ns = ("ops_knowledge",)

    results = store.search(ns, query, limit=5)
    if not results:
        return "未找到相关知识"

    lines = []
    for item in results:
        content = item.value.get("content", "")[:300]
        lines.append(f"## {item.key}\n{content}")
    return "\n\n---\n\n".join(lines)
```

### 6.6 什么数据应该存到 Store

#### ✅ 适合存到 Store 的数据

| 数据类型 | 示例 | namespace 设计 | 为什么不用 AGENTS.md |
|---|---|---|---|
| **运维知识库** | Nginx 调优、Docker 排障、K8s 常见问题 | `("knowledge", "nginx")` | 条目多（100+），全量注入太占 token |
| **历史故障记录** | "2024-01-15 磁盘满导致服务宕机" | `("incidents", "2024-01")` | 需要按时间/关键词搜索 |
| **服务器资产信息** | IP、主机名、角色、环境 | `("assets", "prod")` | 结构化数据，需要按条件查询 |
| **多用户共享数据** | 团队值班表、公共 SOP 文档 | `("team", "sop")` | 跨用户共享，不属于某个人的记忆 |
| **API 配置模板** | 监控阈值、告警规则模板 | `("templates", "alerts")` | 结构化，按需查询 |
| **代码片段库** | 常用脚本、Dockerfile 模板 | `("snippets", "docker")` | 量大，按需搜索 |
| **用户画像（结构化）** | 技能等级、常用工具、项目列表 | `("profile", user_id)` | 结构化数据，比 Markdown 更灵活 |

#### ❌ 不适合存到 Store 的数据

| 数据类型 | 推荐方案 | 原因 |
|---|---|---|
| **用户简单偏好**（"我喜欢简洁回复"） | AGENTS.md | 量少，每次都需要 |
| **项目编码规范** | AGENTS.md | 固定上下文，始终生效 |
| **对话历史** | Checkpointer | 随会话走，不需要跨会话搜索 |
| **临时任务状态** | state["todos"] | 工作记忆，随会话结束而消失 |
| **敏感信息**（密码、Token） | 环境变量/config.yaml | 不应存储在 LLM 可访问的地方 |

### 6.7 Store 的 Namespace 设计

Store 的 namespace 是**分层路径**（tuple），支持层级查询：

```python
# 存储
store.put(("ops_knowledge", "nginx", "tuning"), "memory-tuning", {...})
store.put(("ops_knowledge", "nginx", "security"), "ssl-config", {...})
store.put(("ops_knowledge", "docker", "troubleshoot"), "disk-full", {...})

# 查询：精确 namespace
results = store.search(("ops_knowledge", "nginx", "tuning"), "memory")

# 查询：层级 namespace（包含子级）
results = store.search(("ops_knowledge", "nginx"), "ssl")  # 搜索 nginx 下所有子分类

# 查询：顶级 namespace
results = store.search(("ops_knowledge",), "disk")  # 搜索所有知识
```

Namespace 设计建议：

```
("ops_knowledge", category, subcategory)
├── ("ops_knowledge", "nginx", "tuning")
├── ("ops_knowledge", "nginx", "security")
├── ("ops_knowledge", "docker", "troubleshoot")
├── ("ops_knowledge", "docker", "compose")
├── ("ops_knowledge", "k8s", "debug")
└── ("ops_knowledge", "k8s", "deploy")

("incidents", year, month)
├── ("incidents", "2024", "01")
├── ("incidents", "2024", "02")
└── ...

("profile", user_id)
├── ("profile", "ou_bbcabe6c...")
└── ("profile", "ou_xxx...")
```

### 6.8 Autops 中的 Store 使用建议

| 场景 | namespace | 工具 | 说明 |
|---|---|---|---|
| 运维知识库 | `("knowledge", category)` | `save_knowledge` / `search_knowledge` | Agent 自主积累和查询 |
| 故障记录 | `("incidents", yyyymm)` | `save_incident` / `search_incident` | 历史故障复盘 |
| 服务器资产 | `("assets", env)` | `list_servers` / `get_server` | 替代 config.yaml 中的静态配置 |
| 用户画像 | `("profile", user_id)` | `save_profile` / `get_profile` | 结构化用户偏好 |

### 6.9 向量数据库与 Embedding 模型

#### 两者关系

```
Embedding 模型 = 翻译官
    文本 → 向量（数字序列）
    "Nginx 内存优化" → [0.023, -0.087, 0.156, ...]（1536 维）

向量数据库 = 图书馆书架
    存储向量 + 高效计算向量间距离（相似度）
    返回最相似的 Top-N 结果
```

#### 完整逻辑链

```
写入阶段（存知识）:
    文本 "Nginx 内存优化：调大 worker_connections"
        ↓ Embedding 模型
    向量 [0.023, -0.087, 0.156, ...]（1536 维）
        ↓
    向量数据库存储: 文本 + 向量 + key + namespace

查询阶段（搜知识）:
    查询 "nginx 内存调大"
        ↓ Embedding 模型（同一个模型）
    查询向量 [0.021, -0.083, 0.148, ...]
        ↓
    向量数据库计算余弦相似度，排序返回 Top-5
```

#### 分工对比

| | Embedding 模型 | 向量数据库 |
|---|---|---|
| 角色 | 翻译官 | 图书管理员 |
| 输入 | 文本 | 向量 |
| 输出 | 向量（N 维浮点数） | 相似向量列表 |
| 核心能力 | 理解语义 → 转数字 | 高效计算向量距离 |
| 不知道的 | 不知道存了哪些数据 | 不知道文本含义 |

**关键约束**：写入和查询必须用同一个 Embedding 模型（维度必须匹配），换模型 = 重建所有向量。

#### LangGraph 内置的 Store 实现

| Store | 向量搜索 | 向量数据库 | 适用场景 |
|---|---|---|---|
| `InMemoryStore` | ✅ 纯 Python | 内存 | 开发调试 |
| `PostgresStore` | ✅ pgvector | PostgreSQL 扩展 | 生产 |

**没有独立的 Chroma/Pinecone/Weaviate 实现**，可通过实现 `BaseStore` 自定义。

#### PostgresStore 的向量搜索机制

PostgresStore 使用 **pgvector** 扩展（PostgreSQL 原生向量搜索）：

```sql
-- 自动创建
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE store_vectors (
    store_id BYTEA,
    key TEXT,
    namespace TEXT[],
    embedding vector(1536),   -- 向量列
);

-- 索引类型可选
CREATE INDEX ... USING hnsw (embedding vector_cosine_ops);
```

支持的向量索引：

| 索引 | 特点 | 适用 |
|---|---|---|
| HNSW | 查询快 O(logN)，构建慢，占内存 | 生产推荐 |
| IVFFlat | 构建快，查询稍慢，省内存 | 中等数据量 |
| flat（无索引） | 暴力扫描 | 小数据量（< 10K） |

向量类型：`vector`（float32 标准）/ `halfvec`（float16 省一半内存）

#### Embedding 模型配置

`embed` 参数支持三种形式：

```python
# 1. 字符串 "provider:model"（LangChain init_embeddings 解析）
index={"embed": "openai:text-embedding-3-small", "dims": 1536}

# 2. LangChain Embeddings 对象
from langchain_openai import OpenAIEmbeddings
index={"embed": OpenAIEmbeddings(model="text-embedding-3-small"), "dims": 1536}

# 3. 自定义函数
def my_embed_fn(texts: list[str]) -> list[list[float]]:
    return [...]  # 调用任意 API
index={"embed": my_embed_fn, "dims": 768}
```

#### 常见 Embedding 模型

| 模型 | 维度 | 提供方 | 特点 |
|---|---|---|---|
| text-embedding-3-small | 1536 | OpenAI | 便宜，效果好 |
| text-embedding-3-large | 3072 | OpenAI | 更精准，更贵 |
| bge-large-zh | 1024 | 智源 | 中文效果好，可本地部署 |
| bge-m3 | 1024 | 智源 | 多语言 |

#### 常见向量数据库

| 类型 | 产品 | 特点 |
|---|---|---|
| PG 扩展 | **pgvector** | 复用 PostgreSQL，运维简单 ← LangGraph 内置 |
| 专用向量库 | Milvus | 十亿级向量 |
| | Qdrant | Rust，高性能 |
| | Chroma | 轻量 |
| 云服务 | Pinecone | 全托管 |

#### Autops 推荐

```
Embedding: OpenAI text-embedding-3-small（1536 维）
           或 bge-large-zh（中文好，可本地）
向量库:   pgvector（复用现有 PG，零额外运维）
Store:    PostgresStore（LangGraph 内置集成）
```

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

### 10.3 LocalShellBackend 的安全限制（重要）

**`virtual_mode=True` 只限制文件系统工具（read_file/write_file/ls/grep），不限制 `execute` 工具。**

源码注释明确说明：
```
Commands are executed directly on your host system
using subprocess.run() with shell=True. There is no sandboxing,
isolation, or security restrictions.
- Access any file on the filesystem (regardless of virtual_mode)
- Execute any program or script
- Make network connections
```

| 操作 | virtual_mode 限制 | 安全保障 |
|---|---|---|
| `read_file` / `write_file` | ✅ 限制在 root_dir | virtual_mode |
| `ls` / `grep` / `glob` | ✅ 限制在 root_dir | virtual_mode |
| `execute`（shell 命令） | ❌ **不限制** | 需靠 HITL 或沙箱 |

**安全方案对比**：

| 方案 | 隔离级别 | 依赖 | 适用场景 |
|---|---|---|---|
| `interrupt_on` + 危险命令检测 | 软隔离（人工审批） | 无 | 需要人工监督 |
| `bwrap`（bubblewrap）沙箱 | 硬隔离（mount namespace） | 需安装 bwrap | 自动化执行 |
| `LangSmithSandbox` | 完全隔离（远程容器） | LangSmith | 生产环境 |
| 自定义 `BaseSandbox`（Docker） | 完全隔离 | Docker | 自托管 |

### 10.4 bwrap（bubblewrap）沙箱方案

`bwrap` 通过 mount namespace 实现 `/` → workspace 的映射：

```bash
bwrap --bind workspace / \
      --ro-bind /bin /bin \
      --ro-bind /usr /usr \
      --ro-bind /lib /lib \
      --ro-bind /lib64 /lib64 \
      --dev /dev --proc /proc \
      --tmpfs /tmp \
      /bin/sh -c "<command>"
```

**效果**：
- `pwd` → `/`（workspace 就是根）
- `cat /etc/passwd` → No such file（宿主机隔离）
- `ls /` → 只看到 workspace 文件 + 只读系统目录

**限制**：
- 需要 root 权限（或 CAP_SYS_ADMIN）
- workspace 内没有 `/bin/sh` 时，需 `--ro-bind` 宿主机系统目录

---

## 11. 人工审批（Human-in-the-Loop）

### 11.1 基本用法

通过 `interrupt_on` 参数配置：

```python
agent = create_deep_agent(
    ...,
    interrupt_on={
        "edit_file": True,      # 所有 edit_file 都审批
        "execute": True,        # 所有 execute 都审批
    },
)
```

### 11.2 InterruptOnConfig + when 谓词（动态审批）

`interrupt_on` 支持两种配置形式：

```python
# 形式 1：bool（简单）
interrupt_on={"execute": True}  # 所有 execute 都审批

# 形式 2：InterruptOnConfig（灵活，带 when 谓词）
from langchain.agents.middleware import InterruptOnConfig

interrupt_on={
    "execute": InterruptOnConfig(
        allowed_decisions=["approve", "reject"],
        when=should_interrupt_execute,  # 谓词函数，返回 True 才审批
    ),
}
```

**when 谓词**：

```python
def should_interrupt_execute(request: Any) -> bool:
    """接收 ToolCallRequest 对象，返回 True 触发审批，False 放行。"""
    # ⚠️ 注意：request 是 ToolCallRequest 对象，不是 dict
    # 通过 .tool_call 属性访问 ToolCall dict
    tool_call = getattr(request, "tool_call", None) or {}
    args = tool_call.get("args", {})
    command = args.get("command", "")
    # 自定义判断逻辑
    return is_dangerous(command)
```

**关键点**：
- `when` 接收 `ToolCallRequest` 对象（不是 dict），通过 `.tool_call` 访问内部 dict
- `when` 返回 `True` → 触发 interrupt（审批）
- `when` 返回 `False` → 放行（不审批）
- `when` 返回 `None`（未设置）→ 默认触发审批

### 11.3 三级安全策略

`when` 谓词只能返回 True/False（审批/放行），**不支持"直接拒绝"**。要实现三级策略：

| 级别 | 实现 | 处理方式 |
|---|---|---|
| **高危** | 自定义中间件 `wrap_tool_call` 拦截 | 直接返回错误 ToolMessage，不执行 |
| **危险** | `InterruptOnConfig.when` 返回 True | 触发人工审批 |
| **低风险** | `InterruptOnConfig.when` 返回 False | 放行 |

**高危拦截中间件**：

```python
class CommandSafetyMiddleware(AgentMiddleware):
    def wrap_tool_call(self, request, handler):
        for tc in request.tool_calls:
            if tc["name"] == "execute":
                command = tc["args"]["command"]
                level, reason = assess_command(command)
                if level == "critical":
                    # 直接返回错误，不调用 handler
                    return ToolMessage(
                        content=f"拒绝执行: {reason}",
                        name="execute",
                        tool_call_id=tc["id"],
                        status="error",
                    )
        # 非高危，交给后续中间件处理
        return handler(request)
```

**中间件执行顺序**：
```
CommandSafetyMiddleware（高危拦截）
    ↓ 非高危
HumanInTheLoopMiddleware（when 谓词判断危险/放行）
    ↓ 放行
工具执行
```

### 11.4 工作流程

1. Agent 调用被配置的工具（如 `execute`）
2. `CommandSafetyMiddleware.wrap_tool_call` 检查是否高危
   - 高危 → 直接返回错误 ToolMessage
   - 非高危 → 继续
3. `HumanInTheLoopMiddleware.after_model` 检测到工具调用匹配 `interrupt_on`
4. 调用 `InterruptOnConfig.when` 谓词
   - 返回 True → 构造 `HITLRequest`，调用 `interrupt()` 暂停
   - 返回 False → 放行，直接执行工具
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

---

## 14. Store 落地实践（Autops 三种长期记忆）

本章记录 Autops 项目中实际落地 episodic/semantic/procedural 三种长期记忆工具的经验。

### 14.1 工具与 namespace 实际设计

实际实现位于 `src/autops/store/` 目录：

| 文件 | 工厂函数 | 工具 | Namespace | 隔离 |
|---|---|---|---|---|
| `episodic.py` | `_make_episodic_tools(user_id)` | `save_event` / `search_events` | `("episodic", user_id)` | ✅ 按用户隔离 |
| `semantic.py` | `_make_semantic_tools()` | `save_knowledge` / `search_knowledge` | `("semantic", category)` | ❌ 全局共享 |
| `procedural.py` | `_make_procedural_tools()` | `save_procedure` / `match_procedure` | `("procedural",)` | ❌ 全局共享 |

**工具工厂模式（按用户绑定）**：

episodic 需要按 user_id 隔离，所以用闭包绑定：

```python
def _make_episodic_tools(user_id: str) -> list:
    namespace = ("episodic", user_id)

    @tool
    def save_event(event: str, ..., store: Annotated[BaseStore, InjectedStore()] = None) -> str:
        store.put(namespace, key, value)
        ...

    return [save_event, search_events]
```

semantic 和 procedural 全局共享，直接 `@tool` 装饰即可：

```python
def _make_semantic_tools() -> list:
    @tool
    def save_knowledge(category: str, key: str, value: str, ...) -> str:
        namespace = ("semantic", category)  # 在函数内组装，由参数决定
        store.put(namespace, key, value)
        ...
    return [save_knowledge, search_knowledge]
```

**在 main_agent.py 中组装**：

```python
store = get_store()
if store is not None:
    tools.extend(_make_episodic_tools(uid))   # 情景记忆（按用户隔离）
    tools.extend(_make_semantic_tools())       # 语义记忆（全局共享）
    tools.extend(_make_procedural_tools())    # 程序记忆（全局共享）
```

### 14.2 value 结构与向量索引字段

PostgresStore 的 `index.fields` 指定**哪些 value 字段会被 embedding**。三种记忆的 value 结构都包含一个"检索锚点"字段：

```python
# 初始化时配置（store/__init__.py）
_store = PostgresStore(
    conn=conn,
    index={
        "dims": emb_cfg.dims,
        "fields": ["content", "trigger", "event"],  # ← 三个可能的检索字段
        "embed": _create_embeddings(),
    },
)
```

**三种记忆的 value 结构**：

```python
# episodic 的 value
{
    "type": "episodic",
    "timestamp": "2026-07-16T12:00:00+00:00",
    "event": "修复了 auth.py 的空指针异常",   # ← 检索锚点（在 index.fields 中）
    "context": "用户报告登录 500",
    "outcome": "成功",
    "files": ["auth.py"],
    "tags": ["bugfix", "auth"],
}

# semantic 的 value
{
    "type": "semantic",
    "category": "project_config",
    "key": "tech_stack",
    "value": "Python 3.13, FastAPI, PG",
    "confidence": 1.0,
    "content": "Python 3.13, FastAPI, PG",  # ← 检索锚点（与 value 相同，便于检索）
}

# procedural 的 value
{
    "type": "procedural",
    "trigger": "Docker 容器起不来",          # ← 检索锚点
    "steps": ["docker logs", "docker inspect", ...],
    "description": "标准排障流程",
    "success_rate": 1.0,
    "content": "Docker 容器起不来",          # ← 也作为检索锚点（冗余但兼容）
}
```

**关键**：`fields` 中的字段名必须与 value dict 中的 key 一致，否则 embedding 取不到内容。Store 会**自动**把这些字段的内容拼接后做 embedding 存入向量索引。

### 14.3 JSON 字符串参数兼容（list 转 str）

**问题**：LLM 在调用 `save_event` 时，可能传入：
- JSON 字符串：`'["auth.py", "config.py"]'`
- 逗号分隔：`"auth.py, config.py"`
- 单个文件：`"auth.py"`

**最初设计**：用 `list[str]` 类型注解，但 LangChain 的 tool schema 对 list 参数会要求 LLM 输出 JSON 数组，部分模型（qwen）输出不稳定，导致验证失败。

**最终方案**：参数改为 `str` 类型，内部兼容解析：

```python
@tool
def save_event(
    event: str,
    files: str = "",    # ← 用 str，不用 list[str]
    tags: str = "",
    store: Annotated[BaseStore, InjectedStore()] = None,
) -> str:
    """...
    Args:
        files: 涉及的文件列表（JSON 数组或逗号分隔，如 '["auth.py"]' 或 "auth.py, config.py"）
        tags: 标签列表（JSON 数组或逗号分隔）
    """
    import json as _json
    files_list: list[str] = []
    if files:
        try:
            parsed = _json.loads(files)
            if isinstance(parsed, list):
                files_list = [str(f) for f in parsed]
        except (ValueError, TypeError):
            files_list = [f.strip() for f in files.split(",") if f.strip()]
```

**经验**：对于 LLM 输出不稳定的情况，**用 str + 内部解析**比直接用 `list[str]` 更稳健。

### 14.4 PostgresStore 初始化的正确姿势

**坑**：`PostgresStore.from_conn_string()` 返回的是**上下文管理器**，不能直接当 store 用：

```python
# ❌ 错误：from_conn_string 返回 context manager，不是 store 实例
store = PostgresStore.from_conn_string(
    conn_string="...",
    index={...},
)
# store 是 <contextlib._GeneratorContextManager>, 不是 BaseStore
# 后续 store.put() 会报 AttributeError

# ❌ 错误：with 语法在模块级使用，store 退出 with 后连接关闭
with PostgresStore.from_conn_string(...) as store:
    ...
# 离开 with 块后 store 不可用
```

**正确做法**：直接构造 `PostgresStore(conn=..., index=...)`：

```python
from psycopg import Connection
from psycopg.rows import dict_row
from langgraph.store.postgres import PostgresStore

conn = Connection.connect(
    conn_str,
    autocommit=True,
    prepare_threshold=0,
    row_factory=dict_row,
    options="-c search_path=public",  # 复用 checkpointer 的 schema
)
_store = PostgresStore(
    conn=conn,
    index={
        "dims": emb_cfg.dims,
        "fields": ["content", "trigger", "event"],
        "embed": _create_embeddings(),
    },
)
_store.setup()  # 创建表结构（store 表 + 向量索引）
```

**关键**：
- `autocommit=True`：避免事务管理复杂度
- `prepare_threshold=0`：禁用 prepared statement 缓存（psycopg + PG 兼容性）
- `options="-c search_path=public"`：与 checkpointer 共用同一个 schema
- `setup()` 必须调用，会创建 `store` 表和 `store_vectors` 向量索引表

### 14.5 OpenAI 兼容 Embedding 封装

LangGraph Store 的 `index.embed` 接受 `Embeddings` 对象，但默认只支持 OpenAI 官方模型。要使用阿里 DashScope 的 `text-embedding-v4`，需要自定义封装：

```python
from langchain_core.embeddings import Embeddings

class _OpenAICompatibleEmbeddings(Embeddings):
    """基于 OpenAI 兼容接口的 Embedding 封装。

    支持阿里 DashScope、OpenAI 等所有兼容 OpenAI API 的 embedding 服务。
    """

    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._model = model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        from openai import OpenAI
        client = OpenAI(api_key=self._api_key, base_url=self._base_url)
        resp = client.embeddings.create(model=self._model, input=texts)
        return [item.embedding for item in resp.data]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=self._api_key, base_url=self._base_url)
        resp = await client.embeddings.create(model=self._model, input=texts)
        return [item.embedding for item in resp.data]

    async def aembed_query(self, text: str) -> list[float]:
        result = await self.aembed_documents([text])
        return result[0]
```

**配置（config.yaml）**：

```yaml
store:
  enabled: true
  embedding:
    model: text-embedding-v4
    api_key: "sk-xxx"           # 阿里云百炼 API Key（DASHSCOPE_API_KEY）
    base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
    dims: 1024                  # text-embedding-v4 默认输出 1024 维
```

**关键约束**：
- `dims` 必须与 model 实际输出维度匹配（v4 默认 1024，v3 默认 1536）
- 写入和查询必须用同一个 model，换 model = 重建所有向量
- `aembed_*` 异步方法必须实现（LangGraph dev 异步执行时会调用）

### 14.6 InjectedStore + infer_schema=False 的坑

**问题**：工具用 `InjectedStore` 注入 store 后，如果同时用 `list[str]` 类型注解其他参数，可能触发 `infer_schema=False` 相关的 schema 验证错误。

**现象**：LLM 调用 `save_event` 时报错：
```
ValidationError: field required (type=value_error.missing)
```

**原因**：`InjectedStore` 参数对 LLM 不可见，但 LangChain 在生成 tool schema 时，如果其他参数类型复杂（如 `list[str]`），可能生成错误的 schema。

**解决方案**：
1. 把 `list[str]` 改成 `str` + 内部 JSON 解析（见 14.3）
2. 给 `InjectedStore` 参数加默认值 `= None` 和 `# type: ignore[assignment]`

```python
@tool
def save_event(
    event: str,
    files: str = "",    # ← str 而非 list[str]
    store: Annotated[BaseStore, InjectedStore()] = None,  # type: ignore[assignment]
) -> str:
    ...
```

**经验**：保持工具参数类型简单（str/int/float/bool），复杂结构在函数内部解析。

---

## 15. 路径方案演进与 workspace 隔离

### 15.1 virtual_mode 的路径规则

`LocalShellBackend(virtual_mode=True)` 时，路径解析规则：

| 传入路径 | 实际查找位置 | 能否找到 |
|---|---|---|
| `/memory/AGENTS.md` | `root_dir/memory/AGENTS.md` | ✅ |
| `memory/AGENTS.md` | `root_dir/memory/AGENTS.md` | ✅ 相对路径也行 |
| `/opt/Autops/workspace/memory/AGENTS.md` | `root_dir/opt/Autops/workspace/memory/AGENTS.md` | ❌ 真实绝对路径找不到 |

**关键**：`virtual_mode=True` 把所有路径都当作**相对于 root_dir 的虚拟绝对路径**，真实绝对路径会被拼接到 root_dir 后面，导致嵌套目录找不到文件。

**MemoryMiddleware sources 必须用虚拟路径**：

```python
# ❌ 错误：用真实绝对路径
AlwaysReloadMemoryMiddleware(
    backend=backend,
    sources=["/opt/Autops/workspace/memory/AGENTS.md"],
)

# ✅ 正确：虚拟绝对路径（相对于 backend.root_dir）
AlwaysReloadMemoryMiddleware(
    backend=backend,
    sources=["/memory/AGENTS.md"],
)
```

### 15.2 从绝对路径到相对路径的提示词规范

**问题**：在 virtual_mode 下，Agent 如果用绝对路径（如 `/pgsql.yaml`），文件会被创建在 `root_dir/pgsql.yaml`，看似没问题。但如果用**真实绝对路径**（如 `/opt/Autops/workspace/pgsql.yaml`），文件会被创建在 `root_dir/opt/Autops/workspace/pgsql.yaml`，导致目录嵌套。

**最终方案**：在系统提示词中**强制使用相对路径**：

```
## 工作目录与路径规则

- 你的工作目录（cwd）就是用户的 workspace 根目录。
- **所有文件操作必须使用相对路径**：
  - `write_file(file_path="simple_http_server.py", ...)` ✅
  - `read_file(file_path="pgsql.yaml")` ✅
  - `edit_file(file_path="memory/AGENTS.md", ...)` ✅
  - `write_file(file_path="/opt/Autops/workspace/.../file.py", ...)` ❌ 绝对路径会导致目录嵌套
- **shell 命令也使用相对路径**：
  - `cat pgsql.yaml` ✅
  - `ls` ✅
  - `grep error app.log` ✅
- **不要使用绝对路径**（如 `/pgsql.yaml`、`/etc/passwd`），绝对路径会导致文件创建在错误的嵌套目录中。
```

**经验**：路径安全问题不能只靠代码，**提示词明确规范** + 代码兜底（如 `should_interrupt_execute` 检测 workspace 外路径）双层保障。

### 15.3 workspace 隔离设计

每个用户独立 workspace，通过路径隔离：

```
session/
├── default/                    # LangGraph dev / CLI 用
│   └── workspace/
│       ├── memory/AGENTS.md    # 默认用户长期记忆
│       └── ...                 # 用户文件
├── ou_bbcabe6c962be5aeaa60ed1ca78ceaf4/   # 飞书用户 1
│   └── workspace/
│       ├── memory/AGENTS.md
│       └── ...
└── ou_xxx/                     # 飞书用户 2
    └── workspace/
        └── ...
```

**目录创建时机**（避免 LangGraph dev 的 blockbuster 阻塞检测）：

```python
# 模块级别（线程池中执行，允许阻塞 I/O）
_SESSION_ROOT = Path(config.agent.workspace).resolve() / "session"
_SESSION_ROOT.mkdir(parents=True, exist_ok=True)
_DEFAULT_WORKSPACE = _SESSION_ROOT / "default" / "workspace"
_DEFAULT_WORKSPACE.mkdir(parents=True, exist_ok=True)
(_DEFAULT_WORKSPACE / "memory").mkdir(parents=True, exist_ok=True)

def _get_user_workspace(user_id: str) -> Path:
    """获取用户工作空间路径（不做 I/O）。

    目录由调用方在非事件循环线程中创建（飞书 channel 的处理线程）。
    LangGraph dev 只用 default workspace（模块级别已预创建）。
    """
    if user_id == "default":
        return _DEFAULT_WORKSPACE
    ws = _SESSION_ROOT / user_id / "workspace"
    if not ws.exists():  # 飞书 channel 在独立线程中调用，可以阻塞
        ws.mkdir(parents=True, exist_ok=True)
        (ws / "memory").mkdir(parents=True, exist_ok=True)
    return ws
```

**关键**：
- 模块级别的 mkdir 在**线程池**中执行，blockbuster 不拦截
- 函数内的 mkdir 在**事件循环**中执行，blockbuster 会拦截（报 `BlockingError: os.mkdir`）
- LangGraph dev 只走 `default` 分支（工厂函数无参数）
- 飞书 channel 在独立线程中调用 `_build_agent(user_id=...)`，可以阻塞

---

## 16. 飞书 Channel 集成实践

### 16.1 EventSink 的飞书实现

飞书 channel 实现 `EventSink` 协议，把可观测性事件转发为飞书消息：

```python
class FeishuEventSink:
    """飞书事件 sink — 把 Agent 执行事件发到飞书。"""

    def __init__(self, reporter: FeishuReporter, chat_id: str):
        self._reporter = reporter
        self._chat_id = chat_id

    def notify_tool_start(self, turn: int, tool_name: str, params: str) -> None:
        self._reporter.send_text(
            self._chat_id,
            f"🔄 [Turn {turn}] 调用工具: {tool_name}\n参数: {params[:200]}",
        )

    def notify_tool_end(self, turn: int, tool_name: str, output: str, elapsed: float) -> None:
        self._reporter.send_text(
            self._chat_id,
            f"✅ [Turn {turn}] {tool_name} 完成 ({elapsed:.1f}s)\n结果: {output[:300]}",
        )

    def notify_tool_error(self, turn: int, tool_name: str, error: str, elapsed: float) -> None:
        self._reporter.send_text(
            self._chat_id,
            f"❌ [Turn {turn}] {tool_name} 失败 ({elapsed:.1f}s)\n错误: {error}",
        )

    def notify_summary(self, summary: str) -> None:
        self._reporter.send_text(self._chat_id, summary)
```

**使用方式**：

```python
sink = FeishuEventSink(reporter=reporter, chat_id=chat_id)
handler = AgentObservabilityHandler(sink=sink)
agent.invoke(
    {"messages": [user_msg]},
    config={"thread_id": thread_id, "callbacks": [handler]},
)
# invoke 结束后
handler.summary()  # 内部自动调用 sink.notify_summary
```

### 16.2 审批恢复流程与 handler 重建

`interrupt_on` 触发审批后，Agent 暂停。用户在飞书卡片点击批准后，需要用 `Command(resume=...)` 恢复执行：

```python
# 第一次 invoke（触发 interrupt）
handler1 = AgentObservabilityHandler(sink=sink)
result = agent.invoke(
    {"messages": [user_msg]},
    config={"callbacks": [handler1], "thread_id": thread_id},
)
# result 包含 __interrupt__，handler1.summary() 不会被调用
# 此时飞书发送审批卡片，记录 (thread_id, message_id, user_id) 到 _pending_approvals

# 用户点击批准后，恢复执行（新一轮 LLM 调用）
handler2 = AgentObservabilityHandler(sink=sink)  # ← 新建 handler
result = agent.invoke(
    Command(resume={"decisions": [{"type": "approve"}]}),
    config={"callbacks": [handler2], "thread_id": thread_id},
)
handler2.summary()  # 恢复执行后的统计
```

**关键**：
- 恢复执行是**新一轮 LLM 调用**，需要新建 handler（不复用 handler1）
- token 应单独统计（不与中断前混淆）
- `_pending_approvals` 用 3-tuple `(thread_id, message_id, user_id)` 记录，确保审批卡片与用户对应

### 16.3 群聊与私聊的会话隔离

飞书场景下，`thread_id` 设计为 `chat_id + user_id`：

```python
thread_id = f"{chat_id}_{user_id}"
```

**原因**：
- 同一个群聊中，不同用户的对话应该隔离（A 问的问题 B 不应看到上下文）
- 同一个用户在不同群聊的对话也应隔离（群聊上下文不泄露到私聊）
- `chat_id` 区分群聊/私聊，`user_id` 区分用户

**user_id 用于 workspace 隔离**：

```python
agent = _build_agent(user_id=user_id)
# → workspace = session/{user_id}/workspace/
```

> 注意：飞书的 `open_id`（如 `ou_bbcabe6c962be5aeaa60ed1ca78ceaf4`）是用户唯一标识，群聊和私聊中同一个用户的 `open_id` 相同。这意味着**同一个用户在群聊和私聊中共享同一个 workspace**（但对话上下文通过 `thread_id` 隔离）。

**事件订阅**：
- `im.message.receive_v1` — 接收消息（群聊需 @提及）
- `card.action.trigger` — 接收审批卡片按钮回调

**权限**：
- `im:message` — 发送/接收消息
- `im:message.patches` — 更新已发送的卡片消息（审批后更新状态用）
- `im:message.group_at_msg` — 接收群聊 @ 提及

---

## 17. RAGFlow 知识库集成实践

Autops 项目通过 RAGFlow 实现外部知识库检索。RAGFlow 仅用于**知识检索**（retrieve），不涉及文档管理（上传/解析/切片等由 RAGFlow 平台侧完成）。

### 17.1 架构设计

```
config.yaml (ragflow 配置段)
    ↓
settings.py (RagflowConfig Pydantic 模型)
    ↓
rag/client.py (RAGFlowClient 单例，封装 ragflow_sdk)
    ↓
rag/tools.py (search_rag_knowledge 工具函数)
    ↓
agents/main_agent.py (条件注册工具 + 提示词引导)
```

**模块职责**：

| 文件 | 职责 |
|------|------|
| `config/settings.py` → `RagflowConfig` | 配置解析：enabled、api_key、base_url、dataset_ids、similarity_threshold、top_k |
| `rag/client.py` → `RAGFlowClient` | SDK 封装：全局单例，暴露 `retrieve()` 方法 |
| `rag/tools.py` → `search_rag_knowledge` | Agent 工具：调用 client，格式化输出（含来源、相似度） |
| `agents/main_agent.py` | 条件注册：`if config.ragflow.enabled` 才加载工具 |

### 17.2 配置结构

```yaml
# config.yaml
ragflow:
  enabled: true
  api_key: "ragflow-xxx"
  base_url: "http://10.200.200.105:13120"
  dataset_ids:
    - "89db73d481c411f19f2451e1fbfdeff0"   # 运维知识库
  similarity_threshold: 0.2
  top_k: 5
```

对应 Pydantic 模型：

```python
class RagflowConfig(BaseModel):
    enabled: bool = False
    api_key: str = ""
    base_url: str = "http://127.0.0.1:9380"
    dataset_ids: list[str] = Field(default_factory=list)
    similarity_threshold: float = 0.2
    top_k: int = 5
```

### 17.3 ragflow_sdk 使用要点

**依赖**：`ragflow-sdk>=0.26.0`（pyproject.toml）

**初始化**：

```python
from ragflow_sdk import RAGFlow

rag = RAGFlow(api_key="ragflow-xxx", base_url="http://host:port")
```

**检索**：

```python
chunks = rag.retrieve(
    dataset_ids=["dataset_id"],
    question="用户问题",
    page_size=5,
    similarity_threshold=0.2,
)
# chunk 对象属性: content, similarity, document_name, document_keyword, dataset_name, document_id
```

**列出数据集**（调试用）：

```python
datasets = rag.list_datasets()
for ds in datasets:
    print(ds.id, ds.name)
```

### 17.4 客户端单例模式

```python
_client: RAGFlowClient | None = None

def get_ragflow_client() -> RAGFlowClient | None:
    global _client
    if _client is not None:
        return _client
    # 检查配置 → 创建客户端 → 缓存单例
    ragflow_cfg = config.ragflow
    if not ragflow_cfg.enabled or not ragflow_cfg.api_key:
        return None
    _client = RAGFlowClient(
        api_key=ragflow_cfg.api_key,
        base_url=ragflow_cfg.base_url,
        dataset_ids=ragflow_cfg.dataset_ids,
        similarity_threshold=ragflow_cfg.similarity_threshold,
        top_k=ragflow_cfg.top_k,
    )
    return _client
```

**设计要点**：
- 懒加载：首次调用时才初始化 SDK 连接
- 全局单例：避免重复创建 RAGFlow 连接
- 优雅降级：未启用或配置缺失时返回 None，工具返回提示信息而非报错

### 17.5 工具注册与提示词引导

**条件注册**（main_agent.py）：

```python
from autops.rag.tools import search_rag_knowledge
from autops.config.settings import config as _cfg

tools = [internet_search]
if _cfg.ragflow.enabled:
    tools.append(search_rag_knowledge)
    logger.info("已加载 RAGFlow 知识库检索工具: search_rag_knowledge")
```

**提示词引导**（main_agent.j2）：

```jinja2
## 外部知识库（RAGFlow）
当遇到运维相关问题时，优先使用 `search_rag_knowledge` 工具从知识库检索：
- 运维文档、故障排查方案、操作手册
- 架构说明、配置规范、历史案例
- 任何已沉淀的团队知识
**使用原则**：用户问题涉及已有文档/规范/历史案例时，先检索再回答，避免重复造轮子。
```

### 17.6 与 Store、AGENTS.md 的协作关系

Autops 有三种知识体系，定位各不相同：

| 知识体系 | 注入方式 | 生命周期 | 适用场景 |
|---------|---------|---------|---------|
| AGENTS.md | 始终注入 system prompt | 全局/永久 | Agent 行为规范、核心指令 |
| Store | Agent 按需查询（store_get/store_put） | 会话级/持久化 | 对话中产生的临时知识、用户偏好 |
| RAGFlow | Agent 按需调用 search_rag_knowledge | 外部持久化 | 团队运维文档、操作手册、历史案例 |

**检索优先级建议**：
1. 先判断 AGENTS.md 中是否已有答案（已在上下文中，无需额外调用）
2. 运维知识 → 调用 `search_rag_knowledge`
3. 对话中产生的新知识 → 通过 Store 持久化

### 17.7 踩坑经验

**1. API Key 认证**：
- RAGFlow SDK 使用 `Authorization: Bearer <api_key>` 认证
- API Key 格式为 `ragflow-xxx`，需在 RAGFlow 平台生成
- 遇到 401 时，优先检查 Key 是否过期或被重置

**2. httpx vs ragflow_sdk**：
- 最初尝试用 httpx 直接调 REST API（`POST /api/v1/retrieval`），认证方式难以对齐
- 最终改用 `ragflow_sdk`，与官方保持一致，减少兼容性问题
- **教训**：优先使用官方 SDK，避免自行对接 REST API 的认证细节

**3. retrieve 返回 0 条结果**：
- RAGFlow 的 retrieve 有 `similarity_threshold` 过滤，低于阈值的结果不返回
- 知识库中文档内容要与查询语义相关才能命中
- 调试时先用 `list_datasets()` 确认数据集 ID 正确，再用宽泛的查询测试

**4. 依赖安装的文件锁问题**：
- Windows 下 `uv sync` / `uv add` 可能因进程占用 `.venv` 中的文件而失败
- 解决：`tasklist | grep autops` 找到占用进程 → `taskkill /PID xxx /F` 终止后重试

**5. base_url 格式**：
- 必须包含 `http://` 前缀，如 `http://10.200.200.105:13120`
- 不要以 `/` 结尾
