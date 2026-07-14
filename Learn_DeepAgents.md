# Learn DeepAgents

> 本文件记录 Autops 项目开发过程中学到的 DeepAgents 框架相关知识。

---

## `create_deep_agent` 参数详解

### 函数签名

```python
def create_deep_agent(
    model: str | BaseChatModel | None = None,
    tools: Sequence[BaseTool | Callable | dict[str, Any]] | None = None,
    *,
    system_prompt: str | SystemMessage | None = None,
    middleware: Sequence[AgentMiddleware] = (),
    subagents: Sequence[SubAgent | CompiledSubAgent | AsyncSubAgent] | None = None,
    skills: list[str] | None = None,
    memory: list[str] | None = None,
    permissions: list[FilesystemPermission] | None = None,
    backend: BackendProtocol | BackendFactory | None = None,
    interrupt_on: dict[str, bool | InterruptOnConfig] | None = None,
    response_format: ResponseFormat | type | dict | None = None,
    state_schema: type[DeepAgentState] | None = None,
    context_schema: type | None = None,
    checkpointer: Checkpointer = None,
    store: BaseStore | None = None,
    debug: bool = False,
    name: str | None = None,
    cache: BaseCache | None = None,
) -> CompiledStateGraph
```

---

## 记忆存储三参数对比：`memory` / `checkpointer` / `store`

### 1. `memory` — Agent 长期记忆

**类型**: `list[str] | None`（文件路径列表）

**作用**: 从文件系统加载 `AGENTS.md` 文件内容，注入到 system prompt 的 `<agent_memory>` 块中。Agent 可以"记住"这些文件中的知识，并在运行中通过工具更新这些文件来"学习"。

**处理方式**: deepagents 内部包装为 `MemoryMiddleware`，追加到 middleware 栈：

```python
# graph.py:820-829
if memory is not None:
    deepagent_middleware.append(
        MemoryMiddleware(
            backend=backend,
            sources=memory,        # 文件路径列表
            add_cache_control=True, # Anthropic prompt cache 断点
        )
    )
```

**工作流程**:

1. Agent 启动时，`MemoryMiddleware.before_agent` 通过 `backend.download_files()` 加载所有 `sources` 路径的文件
2. 文件内容存入 `state["memory_contents"]`（`dict[str, str]`，键=路径，值=文件内容）
3. `modify_request` 将内容格式化后追加到 system prompt

**System Prompt 注入格式**:

```
<agent_memory>
{agent_memory}
</agent_memory>

<memory_guidelines>
    The above <agent_memory> was loaded in from files in your filesystem...
    ...（学习反馈、更新记忆的指导）...
</memory_guidelines>
```

**使用示例**:

```python
agent = create_deep_agent(
    model=llm,
    memory=["/memory/AGENTS.md"],  # 加载记忆文件
    backend=backend,
)
```

**特点**:

- 是 deepagents 特有的概念，不是 LangGraph 的
- 文件内容会去掉 HTML 注释（`<!-- -->`）后注入 prompt
- Agent 可以通过 `write_file` 工具更新这些文件，实现"自我学习"
- `add_cache_control=True` 仅对 Anthropic 模型生效，优化 prompt 缓存

---

### 2. `checkpointer` — 对话状态持久化

**类型**: `Checkpointer | None`（来自 `langgraph.types`）

**作用**: 持久化 Agent 的**运行状态**（消息历史、中间变量），支持多轮对话和线程恢复。每个 `thread_id` 对应一个独立的对话上下文。

**处理方式**: 原样透传给 LangGraph 的 `create_agent` → `compile(checkpointer=...)`：

```python
# graph.py:872
return create_agent(
    ...,
    checkpointer=checkpointer,  # 透传
    ...,
)
```

**使用示例**:

```python
from langgraph.checkpoint.memory import MemorySaver
# 或持久化方案：
# from langgraph.checkpoint.sqlite import SqliteSaver
# from langgraph.checkpoint.postgres import PostgresSaver

agent = create_deep_agent(
    model=llm,
    checkpointer=MemorySaver(),  # 内存存储，重启丢失
    # checkpointer=SqliteSaver.from_conn_string("checkpoints.db"),  # 持久化
)
```

**特点**:

- 是 LangGraph 的原生概念，deepagents 不做任何加工
- 通过 `config={"thread_id": "xxx"}` 区分不同会话
- deepagents 的 `DeepAgentState` 用 `DeltaChannel` 优化 messages channel，使 checkpoint 存储增长从 O(N²) 降为 O(N)
- 是 `interrupt_on`（人工审批）的前提条件——interrupt 依赖 checkpointer 保存暂停状态

---

### 3. `store` — 跨线程持久化存储

**类型**: `BaseStore | None`（来自 `langgraph.store.base`）

**作用**: 跨线程的**键值存储**，用于在多个对话之间共享数据。与 `checkpointer` 不同，`store` 不绑定 `thread_id`，可以全局读写。

**处理方式**: 同样原样透传：

```python
# graph.py:873
return create_agent(
    ...,
    store=store,  # 透传
    ...,
)
```

**使用示例**:

```python
from langgraph.store.memory import InMemoryStore
# 或持久化方案：
# from langgraph.store.postgres import PostgresStore

store = InMemoryStore()
agent = create_deep_agent(
    model=llm,
    store=store,  # 跨线程存储
)
```

**特点**:

- 是 LangGraph 的原生概念
- 如果 backend 使用 `StoreBackend`，则 `store` 参数**必需**
- 适合存储用户偏好、全局配置、知识库等跨会话共享的数据

---

### 三者总结对比

| 维度 | `memory` | `checkpointer` | `store` |
|------|----------|----------------|---------|
| **来源** | deepagents 特有 | LangGraph 原生 | LangGraph 原生 |
| **类型** | `list[str]`（文件路径） | `Checkpointer` | `BaseStore` |
| **处理方式** | 包装为 `MemoryMiddleware` | 原样透传 | 原样透传 |
| **存储内容** | AGENTS.md 文件内容（文本） | 对话状态（消息、中间变量） | 任意键值对 |
| **生命周期** | Agent 启动时加载到 prompt | 按 `thread_id` 隔离，每次 invoke 自动保存/恢复 | 跨 `thread_id` 全局共享 |
| **作用域** | 注入 system prompt | 单个对话线程 | 所有对话线程 |
| **典型场景** | 加载项目规范、历史经验 | 多轮对话、中断恢复、人工审批 | 用户偏好、全局知识库 |
| **当前项目** | 未使用 | `MemorySaver` 单例 | 未使用 |

---

## `interrupt_on` — 人工审批（Human-in-the-Loop）

**类型**: `dict[str, bool | InterruptOnConfig] | None`

**作用**: 在指定工具调用前暂停 Agent 执行，等待人工审批后才继续。

**处理方式**: deepagents 内部根据 `interrupt_on` 配置自动添加 `HumanInTheLoopMiddleware`：

```python
# graph.py 示例
interrupt_on={"edit_file": True, "execute": True}
```

**工作流程**:

1. Agent 调用被配置的工具（如 `edit_file`）
2. `HumanInTheLoopMiddleware.after_model` 检测到工具调用匹配 `interrupt_on`
3. 构造 `HITLRequest`（含 `action_requests` 和 `review_configs`）
4. 调用 `interrupt(hitl_request)` 暂停图执行
5. 等待 `Command(resume={"decisions": [...]})` 恢复

**Decision 类型**:

| 类型 | 说明 | 格式 |
|------|------|------|
| `approve` | 批准执行原始参数 | `{"type": "approve"}` |
| `edit` | 修改参数后执行 | `{"type": "edit", "edited_action": {...}}` |
| `reject` | 拒绝，反馈给 Agent | `{"type": "reject", "message": "..."}` |
| `respond` | 直接返回结果，跳过工具 | `{"type": "respond", "value": "..."}` |

**Resume 格式**:

```python
# 恢复执行时传入 Command
agent.invoke(
    Command(resume={"decisions": [{"type": "approve"}]}),
    config={"thread_id": thread_id},
)
```

**注意**:

- `interrupt_on` **依赖 `checkpointer`**——暂停状态需要持久化
- 工厂函数签名必须**无参数**（LangGraph dev 的 `invoke_factory` 会根据参数数量分类工厂类型，有参数的会被注入 config）
- 飞书通道通过 `card.action.trigger` 事件接收审批回调，3 秒内返回 `dict` 响应，Agent 执行放后台线程

---

## `backend` — 文件系统后端

**类型**: `BackendProtocol | BackendFactory | None`

**作用**: 提供文件系统操作（读、写、编辑、搜索、执行命令）的底层实现。

**`LocalShellBackend` 关键参数**:

| 参数 | 说明 |
|------|------|
| `root_dir` | 工作目录根路径，所有文件操作限制在此目录内 |
| `virtual_mode` | `True`: 路径相对于 root_dir（`/` = root_dir）；`False`: 使用真实绝对路径 |
| `timeout` | 命令执行超时（秒） |
| `max_output_bytes` | 输出截断阈值 |
| `inherit_env` | 是否继承宿主机环境变量 |

**`virtual_mode` 踩坑记录**:

- `virtual_mode=True` 时 Agent 应使用虚拟路径（如 `/test.txt`），但 Agent 实际会用真实绝对路径（如 `/opt/Autops/workspace/test.txt`），导致路径双重拼接嵌套
- **解决方案**: 使用 `virtual_mode=False`，Agent 用真实绝对路径，backend 只做沙箱限制

---

## LangGraph Dev 工厂函数签名

LangGraph dev 的 `invoke_factory` 根据参数数量分类工厂函数：

| 参数数 | 分类 | 行为 |
|--------|------|------|
| 0 | 无参 | `value()` 无参调用 ✓ |
| 1 | config 或 runtime | `value(param=config_dict)` 注入参数 |
| 2 | config + runtime | 按类型注解决定参数含义 |

**关键**: 工厂函数必须**无参数**，否则 LangGraph dev 会把 `config` dict 当作第一个参数传入。

```python
# ❌ 错误：有参数，LangGraph dev 会注入 config
def create_main_agent(tools: list | None = None) -> CompiledStateGraph: ...

# ✅ 正确：无参数
def create_main_agent() -> CompiledStateGraph: ...
```

---

## LangGraph Dev 与 blockbuster

LangGraph dev 用 `blockbuster` 检测事件循环中的同步阻塞调用（`os.mkdir`、`open` 等）。

**规则**:

- 模块导入在**线程池**中执行 → blockbuster 不拦截
- 工厂函数在**事件循环**中执行 → blockbuster 拦截阻塞 I/O

**解决方案**: 将阻塞 I/O（如 `os.mkdir`）移到模块级别：

```python
# 模块级别（线程池，安全）
_WORKSPACE = _resolve_workspace()
_WORKSPACE.mkdir(parents=True, exist_ok=True)

def create_main_agent() -> CompiledStateGraph:
    # 事件循环中调用，不能有阻塞 I/O
    return create_deep_agent(...)
```
