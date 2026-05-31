"""
app/database/session.py
========================
数据库会话管理 (PostgreSQL)。

提供三个核心对象:
- engine: 数据库连接池
- SessionLocal: 会话工厂
- Base: ORM 模型基类
- init_db(): 创建所有表

使用方法:
from app.database.session import SessionLocal, init_db
init_db()  # 首次启动时创建表
db = SessionLocal()
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.utils.config import settings

# ---- 创建数据库引擎 ----
# pool_pre_ping=True: 每次使用连接前先测试是否有效 (处理断连)
engine = create_engine(
    settings.database.url,
    pool_size=10,
    pool_pre_ping=True,
)

# ---- 会话工厂 ----
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ---- 声明式基类 ----
# 所有 ORM 模型继承这个 Base
Base = declarative_base()


def init_db():
    """
    创建所有数据库表。

    在应用启动时调用一次。
    Base.metadata.create_all() 会扫描所有继承了 Base 的类,
    在数据库中创建对应的表 (如果表已存在则跳过)。

    使用方式: 在 main.py 的启动事件中调用 init_db()
    """
    # 导入所有模型，确保它们被注册到 Base.metadata
    # 如果不导入，SQLAlchemy 不知道这些类的存在
    import app.database.models  # noqa: F401

    # create_all: 创建所有注册的表
    Base.metadata.create_all(bind=engine)


def get_db():
    """
    FastAPI 依赖注入: 为每个请求提供数据库会话。

    用法:
    @app.get("/jobs")
    def get_jobs(db: Session = Depends(get_db)):
        ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
