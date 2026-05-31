"""
app/utils/config.py
====================
系统配置管理 (Pydantic Settings)。

使用 pydantic-settings 管理所有配置项。
好处:
1. 类型安全: 写错类型 (如 CHUNK_SIZE="abc") 会在启动时报错
2. 自动读取环境变量: 不需要手动 os.getenv()
3. .env 文件支持: 开发时用 .env 文件，部署时用环境变量
4. 嵌套结构: 相关配置分组管理

依赖: pip install pydantic-settings
"""

from pydantic_settings import BaseSettings
from typing import Literal


# ============================================================
# LLM 配置
# ============================================================
# 双模式设计:
# - local:  连接本地 LM Studio (http://localhost:1234/v1)，免费无网络
# - cloud:  连接 DeepSeek API，生产级模型能力
# 两者都是 OpenAI 兼容接口，切换只需改 base_url 和 api_key

class LLMSettings(BaseSettings):
    """
    LLM (大语言模型) 配置。

    通过 llm_mode 切换本地/云端:
    - "local": 使用 LM Studio 本地模型，适合开发调试
    - "cloud": 使用 DeepSeek API 云端模型，适合生产运行
    """

    # 模式切换: "local" 或 "cloud"
    # Literal 类型限制只能选这两个值，输错会在启动时报错
    mode: Literal["local", "cloud"] = "local"

    # --- 本地 LM Studio 配置 ---
    # LM Studio 默认运行在 localhost:1234，提供 OpenAI 兼容 API
    local_base_url: str = "http://localhost:1234/v1"
    # LM Studio 不需要真实的 API Key，填任意字符串即可
    local_api_key: str = "lm-studio"
    # 本地加载的模型名称，需和 LM Studio 中一致
    # 当前使用: qwen3-8b-mlx (8.72 GB, Apple MLX 加速)
    local_model: str = "qwen3-8b-mlx"

    # --- 云端 DeepSeek 配置 ---
    # DeepSeek 是国内性价比最高的 LLM API，中文能力强
    cloud_base_url: str = "https://api.deepseek.com"
    # API Key 从 DeepSeek 平台获取: https://platform.deepseek.com
    cloud_api_key: str = ""
    # DeepSeek 对话模型: deepseek-chat (V3) 或 deepseek-reasoner (R1)
    cloud_model: str = "deepseek-chat"

    # 输出温度 (0=确定性, 1=创造性, 招聘场景建议低温度保证稳定性)
    temperature: float = 0.1

    # 最大输出 token 数
    # qwen3-8b-mlx 是 thinking 模型，内部推理消耗大量 token
    # 本地模型建议 4096，给推理留空间；云端 2048 够用
    max_tokens: int = 4096

    class Config:
        env_prefix = "LLM_"


class EmbeddingSettings(BaseSettings):
    """
    Embedding (文本向量化) 配置。

    设计思路和 LLM 一样: local 免费开发 + cloud 生产部署。
    LM Studio 也支持 embedding 模型。
    """

    mode: Literal["local", "cloud"] = "local"

    # 本地
    local_base_url: str = "http://localhost:1234/v1"
    local_api_key: str = "lm-studio"
    # 当前使用: text-embedding-qwen3-embedding-4b (2.50 GB)
    local_model: str = "text-embedding-qwen3-embedding-4b"

    # 云端
    cloud_base_url: str = "https://api.deepseek.com"
    cloud_api_key: str = ""
    cloud_model: str = "deepseek-embedding"

    # 向量维度 (取决于模型，不同模型维度不同)
    # text-embedding-qwen3-embedding-4b: 2560
    # DeepSeek embedding: 1536
    dimension: int = 2560

    class Config:
        env_prefix = "EMBEDDING_"


# ============================================================
# 数据库配置
# ============================================================

class DatabaseSettings(BaseSettings):
    """
    数据库配置。

    使用 PostgreSQL:
    - 默认连接: postgresql://用户名:密码@主机:端口/数据库名
    - Docker Compose 启动时，PostgreSQL 服务的 host 是 "postgres"
    """

    # 数据库连接 URL
    # 格式: postgresql://user:password@host:port/database
    url: str = "postgresql://hireflow:hireflow@localhost:5432/hireflow"

    class Config:
        env_prefix = "DB_"


class QdrantSettings(BaseSettings):
    """
    Qdrant 向量数据库配置。

    Qdrant 是一个高性能的向量搜索引擎，用 Rust 编写。
    - 默认运行在 localhost:6333
    - Docker Compose 中服务名是 "qdrant"
    """

    url: str = "http://localhost:6333"
    # Qdrant 云端需要 API Key，本地部署留空
    api_key: str = ""

    class Config:
        env_prefix = "QDRANT_"


# ============================================================
# 文档处理配置
# ============================================================

class DocumentSettings(BaseSettings):
    """
    文档处理配置。
    """

    # 文本切分的 chunk 大小 (字符数)
    # RecursiveCharacterTextSplitter 会尽量在句子/段落边界切分
    chunk_size: int = 500
    # 相邻 chunk 之间的重叠字符数，防止关键信息被切在边界处
    chunk_overlap: int = 50

    class Config:
        env_prefix = "DOC_"


# ============================================================
# 日志配置
# ============================================================

class LogSettings(BaseSettings):
    """日志配置。"""
    level: str = "INFO"

    class Config:
        env_prefix = "LOG_"


# ============================================================
# 全局配置聚合
# ============================================================

class Settings(BaseSettings):
    """
    全局配置聚合类。

    把所有子配置聚合到一起，使用时:
    from app.utils.config import settings
    print(settings.llm.mode)  # "local" 或 "cloud"
    """

    llm: LLMSettings = LLMSettings()
    embedding: EmbeddingSettings = EmbeddingSettings()
    database: DatabaseSettings = DatabaseSettings()
    qdrant: QdrantSettings = QdrantSettings()
    document: DocumentSettings = DocumentSettings()
    log: LogSettings = LogSettings()

    class Config:
        # 从 .env 文件加载环境变量 (开发环境)
        env_file = ".env"
        env_file_encoding = "utf-8"


# --- 创建全局配置实例 ---
# 导入这个 settings 对象即可使用所有配置
# 例如: settings.llm.mode, settings.database.url
settings = Settings()
