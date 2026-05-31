"""
app/database/session.py
========================
数据库会话管理 (PostgreSQL)。

使用 SQLAlchemy 管理 PostgreSQL 数据库连接。
PostgreSQL 通过 Docker Compose 启动，默认端口 5432。

核心概念:
- engine: 数据库引擎，管理连接池
- SessionLocal: 会话工厂，每次请求创建一个新会话
- get_db(): FastAPI 依赖注入函数，请求结束自动关闭会话
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.utils.config import settings

# ---- 创建数据库引擎 ----
# create_engine() 创建一个数据库连接池
# pool_size: 连接池默认大小
# pool_pre_ping: 每次使用连接前先 ping 一下，确保连接有效 (处理断连问题)
engine = create_engine(
    settings.database.url,
    pool_size=10,
    pool_pre_ping=True,
    # echo=True 会打印所有 SQL 语句，调试时打开
    # echo=True,
)

# ---- 创建会话工厂 ----
# sessionmaker 是一个工厂函数，每次调用都创建一个新的数据库会话
# autocommit=False: 需要手动 commit()，避免意外提交
# autoflush=False: 需要手动 flush()，更好控制数据何时写入
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ---- 声明式基类 ----
# 所有 ORM 模型都继承这个 Base 类
# from app.database.session import Base
# class Job(Base): ...
Base = declarative_base()


def get_db():
    """
    FastAPI 依赖注入函数: 每个请求获取一个数据库会话。

    用法:
    @app.get("/jobs")
    def get_jobs(db: Session = Depends(get_db)):
        return db.query(Job).all()

    这个函数会在请求结束时自动关闭会话 (finally 块)。
    """
    # 创建一个新的数据库会话
    db = SessionLocal()
    try:
        # yield 把会话交给调用者使用
        yield db
    finally:
        # 无论请求成功还是失败，都确保关闭会话释放连接
        db.close()
