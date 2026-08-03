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
from dotenv import load_dotenv
import os

# 手动加载 .env 文件到 os.environ
# Pydantic Settings 嵌套模型读 .env 有时不稳定, 用 dotenv 确保加载
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"))


# ============================================================
# LLM 配置
# ============================================================
# 双模式设计:
# - local: 连接本地 LM Studio (hermes-3-llama-3.1-8b)
# - cloud: 连接 DeepSeek API (deepseek-v4-pro)
# 两者都是 OpenAI 兼容接口

# BaseSettings 是由 pydantic-settings 库提供的一个基类（模板类）
class LLMSettings(BaseSettings):
    """
    LLM 配置。

    mode 切换:
    - "local": hermes-3-llama-3.1-8b, 结构化输出用 json_schema
    - "cloud": deepseek-v4-pro, 结构化输出用 function_calling (需关 thinking)
    """

    # Literal-字面量
    # 用来把变量的取值范围死死限制在指定的几个固定值里面，多一个少一个都不行
    mode: Literal["local", "cloud"] = "local"

    # --- 本地 LM Studio ---
    local_base_url: str = "http://localhost:1234/v1"
    local_api_key: str = "lm-studio"
    local_model: str = "hermes-3-llama-3.1-8b"

    # --- 云端 DeepSeek ---
    cloud_base_url: str = "https://api.deepseek.com/v1"
    cloud_api_key: str = ""  # 从 .env 读取, 不要硬编码
    cloud_model: str = "deepseek-v4-flash"

    # 输出温度
    temperature: float = 0.1

    # 最大输出 token (本地模型无 thinking, 2048 够用)
    max_tokens: int = 2048

    # 在 Pydantic 中，class Config 是一个 配置舱（或者叫内部配置类）
    class Config:
        # env_prefix->告诉系统：在外面的 .env 文件或者系统环境变量里找配置时，请在变量名的前面自动加上 LLM_ 这个前缀再去找。
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
    cloud_api_key: str = ""  # 从 .env 或环境变量读取
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
    """日志等级配置。"""

    level: str = "INFO"

    class Config:
        env_prefix = "LOG_"


# ============================================================
# 受控 ReAct 证据 Agent 配置
# ============================================================

class EvidenceAgentSettings(BaseSettings):
    """
    证据 Agent 的执行预算和重试策略。

    所有数值都可以通过 EVIDENCE_AGENT_ 前缀环境变量覆盖，便于在本地模型
    和云端模型之间分别调节速度与稳定性。
    """

    # 最多执行 3 次模型决策，防止 ReAct 循环无限运行。
    max_iterations: int = 3
    # 一次候选人检索最多执行 6 个 Tool Call。
    max_tool_calls: int = 6
    # 总尝试次数包含第一次调用，因此 3 表示最多自动重试两次。
    max_attempts: int = 3
    # 第一次重试等待 0.5 秒，之后按 2 倍指数退避。
    initial_retry_interval: float = 0.5
    # 模型连续两次生成非法工具参数后停止并交给人工。
    max_correctable_errors: int = 2

    class Config:
        env_prefix = "EVIDENCE_AGENT_"


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
    evidence_agent: EvidenceAgentSettings = EvidenceAgentSettings()

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        # extra="ignore": 忽略环境变量中不属于 Settings 顶层字段的值
        # 因为 DB_URL, DOC_CHUNK_SIZE 等属于嵌套的子 Settings，
        # 它们通过各自的 env_prefix 来匹配，不需要在顶层再定义一次
        extra = "ignore"


settings = Settings()
