"""配置加载模块 — 从 config.yaml 读取项目配置。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

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
    max_tokens: int = 4096


class AgentConfig(BaseModel):
    """Agent 运行参数。"""

    max_iterations: int = 15
    recursion_limit: int = 100
    workspace: str = ""


class FeishuConfig(BaseModel):
    """飞书 Bot 配置（WebSocket 长连接模式）。"""

    app_id: str = ""
    app_secret: str = ""
    encrypt_key: str = ""


class AppConfig(BaseModel):
    """全局应用配置。"""

    log_level: str = "INFO"
    llm: LLMConfig = Field(default_factory=LLMConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    feishu: FeishuConfig = Field(default_factory=FeishuConfig)

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
