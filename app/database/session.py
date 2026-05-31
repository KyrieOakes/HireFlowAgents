"""
app/database/session.py
========================
数据库会话管理。

管理数据库连接的生命周期。
使用 SQLAlchemy 的 sessionmaker 创建线程安全的数据库会话。
"""

# TODO: 实现数据库连接管理
# from sqlalchemy import create_engine
# from sqlalchemy.orm import sessionmaker

# 数据库 URL: SQLite 用于 MVP，后续迁移到 PostgreSQL
# SQLite 是文件型数据库，无需额外安装服务
# DATABASE_URL = "sqlite:///./hireflow.db"

# 创建数据库引擎
# engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# 创建会话工厂
# SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 依赖注入函数: 每个请求获取一个数据库会话，请求结束后自动关闭
# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()
