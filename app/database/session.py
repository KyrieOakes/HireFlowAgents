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
# pool_pre_ping=True: 每次使用 连接前 先测试是否有效 (处理断连)
# create_engine -> 创建与数据库 通信 的 底层引擎
engine = create_engine(
    settings.database.url,
    # 连接池（Connection Pool）的大小
    # 后端会同时维持 10 条与数据库的物理连接通道
    pool_size=10,
    # 每次用管道传数据前，先测试，看管道 是否正常
    pool_pre_ping=True,
)

# ---- 会话工厂 ----
# sessionmaker 是干啥的：专门用来批量生产 Session（会话）对象的
# autocommit=False：“不要自动提交” - 我们在写简历或职位数据时，必须手动执行 db.commit()，数据库才会真正保存。这可以防止写到一半出错时，脏数据被意外存入
# autoflush=False：“不要自动刷新”。不让它每次改一点点数据就 频繁去同步数据库，等我们说同步时再同步，提高效率
# bind=engine：把这个水龙头工厂和上面那条输水管线（engine）绑在一起
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ---- 声明式基类 ----
# 所有 ORM（对象关系映射） 模型继承这个 Base
# 像一张 图纸总规划。所有要在数据库里建的表（职位、简历），都必须画在这张图纸上
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
    # 拿着画满所有表结构的图纸（Base.metadata），
    # 顺着管线（engine）去 PostgreSQL 数据库里瞅一眼。
    # 如果发现数据库里还没有这些表，就自动把它们全部建立出来；
    # 如果有了，就直接跳过
    Base.metadata.create_all(bind=engine)


def get_db():
    """
    FastAPI 依赖注入: 为每个请求提供数据库会话。

    用法:
    @app.get("/jobs")
    def get_jobs(db: Session = Depends(get_db)):
        ...
    """
    # 创建 数据库会话 - 打开一个 数据库操作通道
    db = SessionLocal()
    try:
        # 先把数据库 session 给你用，用的过程中可能出错，但没关系，最后一定会收尾
        yield db
    finally:
        db.close()
