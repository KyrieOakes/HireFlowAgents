"""
app/utils/config.py
====================
系统配置管理。

集中管理所有配置项，从环境变量或配置文件读取。
使用单一配置来源，避免在代码中硬编码配置值。
"""

import os


# ---- LLM 配置 ----
# 从环境变量读取 API Key，避免将密钥硬编码在代码中
# os.getenv("变量名", "默认值"): 第一个参数是要读取的环境变量名，
#   第二个参数是当环境变量不存在时使用的默认值
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
# 使用的 LLM 模型名称
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")

# ---- 数据库配置 ----
# SQLite 文件路径 (MVP 阶段使用)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./hireflow.db")

# ---- 向量数据库配置 ----
# 向量数据库类型: "chroma" / "qdrant" / "faiss"
VECTOR_STORE_TYPE = os.getenv("VECTOR_STORE_TYPE", "chroma")
# 向量存储路径 (本地 Chroma 使用)
VECTOR_STORE_PATH = os.getenv("VECTOR_STORE_PATH", "./vector_db")

# ---- 文档处理配置 ----
# 文本切分的 chunk 大小 (字符数)
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))
# chunk 之间的重叠字符数
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))

# ---- 日志配置 ----
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
