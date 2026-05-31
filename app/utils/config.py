"""
app/utils/config.py
====================
系统配置管理 (Pydantic Settings)。

使用 pydantic-settings 管理所有配置项。
好处:
1. 类型安全: 写错类型 (如 CHUNK_SIZE="abc") 会在启动时报错
2. 自动读取环境变量: 不需要手动 os.getenv()
3. .env 文件支持: 开发时用 .env 文件，部署时用环境变量

依赖: pip install pydantic-settings
"""

from pydantic_settings import BaseSettings
from typing import Literal


# ============================================================
# LLM 配置
# ============================================================
# 双模式设计:
# - local: 连接本地 LM Studio (hermes-3-llama-3.1-8b)
# - cloud: 连接 DeepSeek API (deepseek-v4-pro)
# 两者都是 OpenAI 兼容接口

class LLMSettings(BaseSettings):
    """
    LLM 配置。

    mode 切换:
    - "local": hermes-3-llama-3.1-8b, 结构化输出用 json_schema
    - "cloud": deepseek-v4-pro, 结构化输出用 function_calling (需关 thinking)
    """

    mode: Literal["local", "cloud"] = "local"

    # --- 本地 LM Studio ---
    local_base_url: str = "http://localhost:1234/v1"
    local_api_key: str = "lm-studio"
    local_model: str = "hermes-3-llama-3.1-8b"

    # --- 云端 DeepSeek ---
    cloud_base_url: str = "https://api.deepseek.com/v1"
    cloud_api_key: str = "sk-595f9fce6d5245cfa00168b760217d40"
    cloud_model: str = "deepseek-v4-pro"

    # 输出温度
    temperature: float = 0.1

    # 最大输出 token (本地模型无 thinking, 2048 够用)
    max_tokens: int = 2048

    class Config:
        env_prefix = "LLM_"


class EmbeddingSettings(BaseSettings):
    """
    Embedding 配置。

    - local: text-embedding-qwen3-embedding-4b (2560维)
    - cloud: DeepSeek embedding (1536维, 暂未配置)
    """

    mode: Literal["local", "cloud"] = "local"

    # 本地
    local_base_url: str = "http://localhost:1234/v1"
    local_api_key: str = "lm-studio"
    local_model: str = "text-embedding-qwen3-embedding-4b"

    # 云端
    cloud_base_url: str = "https://api.deepseek.com/v1"
    cloud_api_key: str = "sk-595f9fce6d5245cfa00168b760217d40"
    cloud_model: str = "deepseek-embedding"

    # 向量维度: qwen3-embedding = 2560, DeepSeek = 1536
    dimension: int = 2560

    class Config:
        env_prefix = "EMBEDDING_"


# ============================================================
# 数据库配置
# ============================================================

class DatabaseSettings(BaseSettings):
    """PostgreSQL 数据库配置。"""
    url: str = "postgresql://hireflow:hireflow@localhost:5432/hireflow"

    class Config:
        env_prefix = "DB_"


class QdrantSettings(BaseSettings):
    """Qdrant 向量数据库配置。"""
    url: str = "http://localhost:6333"
    api_key: str = ""

    class Config:
        env_prefix = "QDRANT_"


# ============================================================
# 文档处理
# ============================================================

class DocumentSettings(BaseSettings):
    """文档处理配置。"""
    chunk_size: int = 500
    chunk_overlap: int = 50

    class Config:
        env_prefix = "DOC_"


# ============================================================
# 日志
# ============================================================

class LogSettings(BaseSettings):
    level: str = "INFO"

    class Config:
        env_prefix = "LOG_"


# ============================================================
# 全局配置
# ============================================================

class Settings(BaseSettings):
    llm: LLMSettings = LLMSettings()
    embedding: EmbeddingSettings = EmbeddingSettings()
    database: DatabaseSettings = DatabaseSettings()
    qdrant: QdrantSettings = QdrantSettings()
    document: DocumentSettings = DocumentSettings()
    log: LogSettings = LogSettings()

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
