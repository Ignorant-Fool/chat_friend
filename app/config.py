"""应用配置：从环境变量 / .env 读取模型与存储配置。

使用 pydantic-settings 提供类型化的配置对象，便于在项目各处引用。
通过 ``validation_alias`` 让 ``DEEPSEEK_*`` 环境变量（.env 内同名前缀）
正确映射到 ``llm_*`` 字段。
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录 = 本文件向上两级 (app/config.py -> app -> 项目根)
ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """全局配置。

    字段名 ``llm_api_key`` 对应环境变量 / .env 中的 ``DEEPSEEK_API_KEY``。
    """

    # --- 模型（DeepSeek，OpenAI 兼容协议）---
    llm_api_key: str = Field(
        default="", validation_alias="DEEPSEEK_API_KEY"
    )
    llm_base_url: str = Field(
        default="https://api.deepseek.com", validation_alias="DEEPSEEK_BASE_URL"
    )
    llm_model: str = Field(
        default="deepseek-chat", validation_alias="DEEPSEEK_MODEL"
    )
    llm_temperature: float = 0.7
    llm_max_tokens: int = 1024

    # --- 存储 ---
    db_path: Path = Field(default=ROOT_DIR / "data" / "chat_friend.db", validation_alias="DB_PATH")
    auto_create_tables: bool = Field(default=True, validation_alias="AUTO_CREATE_TABLES")

    # --- 应用 ---
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,  # 也允许用字段名本身（llm_api_key）传入
    )


@lru_cache
def get_settings() -> Settings:
    """返回缓存的全局配置单例。"""
    return Settings()


settings = get_settings()
