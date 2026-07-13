# Autops — CodeBuddy 项目指令

> 本文件为 CodeBuddy 提供项目上下文和开发规范，全文自动加载到对话上下文中。

## 项目概述

Autops 是一个基于 [Deepagents](https://github.com/langchain-ai/deepagents) 框架的 SRE/DevOps AI Agent 智能体。它能够理解自然语言指令，自主规划任务步骤，并通过工具调用完成运维自动化。

- **语言**：Python 3.13+
- **包管理**：uv
- **核心框架**：Deepagents 0.6.x（基于 LangGraph + LangChain）
- **LLM**：兼容 OpenAI / Anthropic / Google 等模型

## 项目结构

```
src/autops/
├── agents/      # 智能体定义（主 Agent + 子 Agent，基于 create_deep_agent）
├── channels/    # 通信渠道（CLI / API / Webhook 交互入口）
├── config/      # 从 config.yaml 加载全局配置
├── llm/         # LLM 客户端封装（LangChain 聊天模型）
├── prompts/     # 提示词与 Jinja2 模板
│   ├── renderer.py   # 模板渲染引擎
│   ├── system.py     # 提示词构建函数
│   └── templates/    # .j2 模板文件目录
└── tools/       # SRE/DevOps 工具集（shell/system/logs/docker/network/git_ops）
```

## 编码规范

### 代码风格

- 使用 **ruff** 进行 lint 和格式化，行宽上限 100
- 所有模块使用 `from __future__ import annotations` 以支持延迟类型求值
- 公共函数和类必须有 docstring，使用中文描述
- 类型注解必填，使用 Python 3.13+ 语法（`list[str]` 而非 `List[str]`）

### 命名约定

- 模块文件：`snake_case.py`
- 类：`PascalCase`
- 函数/变量：`snake_case`
- 常量：`UPPER_SNAKE_CASE`
- Agent 工具函数：动词开头，如 `run_shell`、`check_system`、`analyze_logs`

### 工具开发规范

每个工具模块应遵循以下模式：

```python
from __future__ import annotations

def tool_function(param: str) -> str:
    """工具的简短描述（Agent 会读取此 docstring 决定是否调用）。

    Args:
        param: 参数说明

    Returns:
        返回值的说明
    """
    # 实现
    return result
```

- 工具函数返回 **字符串**，便于 LLM 直接消费
- 危险操作（删除文件、重启服务）应在函数内加入确认逻辑或明确警告
- 命令执行类工具需设置超时，默认 30 秒
- 输出超过 8000 字符时截断并提示

## 架构说明

### Agent 创建

使用 Deepagents 的 `create_deep_agent` 创建智能体：

```python
from deepagents import create_deep_agent
from autops.llm.client import create_llm
from autops.prompts.system import get_main_agent_prompt

agent = create_deep_agent(
    model=create_llm(),
    tools=[...],
    system_prompt=get_main_agent_prompt(),
)
```

### 提示词模板

所有提示词使用 Jinja2 模板（`.j2`），存放在 `prompts/templates/` 目录下：

```python
from autops.prompts.renderer import render_prompt

# 渲染模板，支持传入变量
prompt = render_prompt("main_agent.j2", agent_name="Autops", capabilities=[...])
```

### 模块依赖关系

```
channels/ → agents/ → llm/, prompts/, tools/
               ↓
            config/（全局配置）
```

- `config/` 是最底层模块，被所有其他模块依赖
- `llm/` 封装模型客户端，供 `agents/` 使用
- `prompts/` 提供提示词，供 `agents/` 使用
- `tools/` 定义工具函数，供 `agents/` 注册
- `channels/` 是最上层，组装 Agent 并提供交互入口

## 常用命令

```bash
# 安装依赖
uv sync

# 添加新依赖
uv add <package>

# 运行项目
uv run autops

# Lint 检查
uv run ruff check src/

# 运行测试
uv run pytest
```

## 注意事项

- **文档同步**：每次重要更新或变更后，必须同步更新 `README.md`，保持文档与代码一致
- **安全模型**：Deepagents 采用"信任 LLM"模式，安全边界应在工具/沙箱层面强制执行，而非依赖模型自我约束
- **配置文件**：敏感信息（API key 等）放在 `config.yaml` 中，已加入 `.gitignore`，不要提交到 Git
- **Python 版本**：项目要求 Python >= 3.13，使用 uv 管理虚拟环境
- **Deepagents API**：核心入口是 `create_deep_agent(model, tools, system_prompt)`，参考 [官方文档](https://github.com/langchain-ai/deepagents)
