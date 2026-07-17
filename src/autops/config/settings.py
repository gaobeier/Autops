"""配置加载模块 — 从 .env 和 config.yaml 读取项目配置。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# 加载 .env 环境变量（LANGSMITH_API_KEY 等），在读取 config.yaml 之前执行
load_dotenv()

# 日志级别字符串 → logging 常量的映射
_LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


class LLMConfig(BaseModel):
    """LLM 模型配置。"""

    provider: str = "openai"
    model: str = "qwen3.7-plus"
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    temperature: float = 0.7
    # max_tokens: int = 4096


class SafetyConfig(BaseModel):
    """命令安全策略配置（可通过 config.yaml 灵活配置）。"""

    # 危险命令正则列表（匹配则触发人工审批）
    # 高危命令（rm -rf /、dd 写裸盘等）在代码中硬编码，不可配置
    dangerous_commands: list[str] = [
        r"\brm\b",
        r"\brmdir\b",
        r"\bunlink\b",
        r"\bshred\b",
        r"\bshutdown\b",
        r"\breboot\b",
        r"\bhalt\b",
        r"\bpoweroff\b",
        r"\binit\s+0\b",
        r"\binit\s+6\b",
        r"\bdd\b",
        r"\bmkfs\b",
        r"\bfdisk\b",
        r"\bparted\b",
        r"\bmount\b",
        r"\bumount\b",
        r"\buseradd\b",
        r"\buserdel\b",
        r"\busermod\b",
        r"\bpasswd\s+\S",
        r"\bchown\b",
        r"\bchmod\b.*\b[0-7]{3,4}\b",
        r"\bsudo\b",
        r"\bsu\b\s+",
        r"\bvisudo\b",
        r"\bsystemctl\b.*(stop|disable|restart|kill)",
        r"\bservice\b.*(stop|restart)",
        r"\bkill\b",
        r"\bkillall\b",
        r"\bpkill\b",
        r"\biptables\b",
        r"\bfirewall-cmd\b",
        r"\bufw\b",
        r"\bnft\b",
        r"\bapt\b.*(install|remove|purge|upgrade)",
        r"\byum\b.*(install|remove|erase)",
        r"\bdnf\b.*(install|remove|erase)",
        r"\bpip\b.*install",
        r"\bnpm\b.*install",
        r"\bdocker\b.*(rm|stop|kill|rmi|prune)",
        r"\bkubectl\b.*delete",
    ]

    # 危险路径正则列表（匹配则触发人工审批）
    # 留空则使用默认逻辑：workspace 外的绝对路径都视为危险
    dangerous_paths: list[str] = []


class AgentConfig(BaseModel):
    """Agent 运行参数。"""

    max_iterations: int = 15
    recursion_limit: int = 100
    workspace: str = "./workspace"
    safety: SafetyConfig = Field(default_factory=SafetyConfig)


class FeishuConfig(BaseModel):
    """飞书 Bot 配置（WebSocket 长连接模式）。"""

    app_id: str = ""
    app_secret: str = ""
    encrypt_key: str = ""


class PostgresConfig(BaseModel):
    """PostgreSQL 配置（用于 checkpointer 持久化）。"""

    host: str = "127.0.0.1"
    port: int = 5432
    user: str = ""
    password: str = ""
    database: str = ""


class EmbeddingConfig(BaseModel):
    """Embedding 模型配置（用于 Store 向量检索）。"""

    model: str = "text-embedding-v4"
    api_key: str = ""
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    dims: int = 1024  # text-embedding-v4 默认输出 1024 维


class StoreConfig(BaseModel):
    """Store 配置（跨会话共享的键值存储，支持向量检索）。"""

    enabled: bool = False
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)


class AppConfig(BaseModel):
    """全局应用配置。"""

    log_level: str = "INFO"
    llm: LLMConfig = Field(default_factory=LLMConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    feishu: FeishuConfig = Field(default_factory=FeishuConfig)
    postgres: PostgresConfig = Field(default_factory=PostgresConfig)
    store: StoreConfig = Field(default_factory=StoreConfig)

    @property
    def logging_level(self) -> int:
        """将 log_level 字符串转换为 logging 常量。"""
        return _LOG_LEVELS.get(self.log_level.upper(), logging.INFO)


def _find_config_file() -> Path:
    """查找 config.yaml，优先项目根目录。"""
    candidates = [
        Path.cwd() / "config.yaml",
        Path.cwd() / "config.yml",
        Path(__file__).resolve().parents[3] / "config.yaml",
    ]
    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError(
        "未找到 config.yaml 配置文件，请在项目根目录创建。"
    )


def load_config() -> AppConfig:
    """加载 config.yaml 并返回 AppConfig 对象。

    Returns:
        解析后的 AppConfig 实例。
    """
    config_path = _find_config_file()
    with open(config_path, encoding="utf-8") as f:
        raw: dict[str, Any] = yaml.safe_load(f) or {}
    return AppConfig(**raw)


# 全局配置单例（首次导入时加载）
config = load_config()
