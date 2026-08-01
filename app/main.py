"""
app/main.py
============
FastAPI 应用入口。

HireFlow 后端服务的启动文件。
启动方式: uvicorn app.main:app --reload

启动时自动:
- 初始化数据库 (创建所有表)
- 注册 API 路由
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 导入数据库初始化函数
from app.database.session import init_db

# 导入 API 路由模块
from app.api import jobs, resumes, matching, workflow, interview, evaluation


# ================================================================
# 应用生命周期管理
# ================================================================
# @asynccontextmanager 定义一个异步上下文管理器
# yield 之前的代码在应用启动时运行
# yield 之后的代码在应用关闭时运行

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理。

    启动时: 初始化数据库，创建所有表。
    关闭时: 清理资源 (暂无)。
    """
    # 启动: 创建数据库表
    print("[HireFlow] 正在初始化数据库...")
    init_db()
    print("[HireFlow] 数据库初始化完成")
    print("[HireFlow] API 服务已启动")

    # yield 交出控制权给 FastAPI
    yield

    # 关闭时的清理 (暂无需要清理的资源)
    print("[HireFlow] 正在关闭...")


# ================================================================
# 创建 FastAPI 应用
# ================================================================

app = FastAPI(
    title="HireFlow API",
    description="HireFlow: 基于 LangGraph 的多 Agent 招聘筛选与面试辅助系统",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS 中间件: 允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许 所有网站（源）来访问我
    allow_credentials=True, # 是否允许前端请求携带凭证（比如 Cookies、授权 Header、TLS 客户端证书等）
    
    # 允许前端使用哪些 HTTP 方法（请求方式）
    # 前端用 GET（获取数据）、POST（提交数据）、PUT（修改数据）、DELETE（删除数据）等任何方式发请求，后端都放行
    allow_methods=["*"], 

    # 允许前端在请求头（Headers）里携带哪些自定义信息
    # 前端可以在请求里自由地塞入各种自定义的 Header 参数（比如用来鉴权的 Token），后端都不会拦截
    allow_headers=["*"],
)

# ================================================================
# 注册 API 路由
# ================================================================
# include_router: 将路由模块挂载到应用上
# 每个模块处理一类 API 端点

app.include_router(jobs.router)
app.include_router(resumes.router)
app.include_router(matching.router)
app.include_router(workflow.router)
app.include_router(interview.router)
app.include_router(evaluation.router)


# ================================================================
# 根路径: 健康检查
# ================================================================

# / 代表根路径（也叫主页、首页）。比如你的后端服务运行在 http://127.0.0.1:8000，那么当你直接在浏览器访问这个网址时，触发的就是 /
@app.get("/")
async def root():
    """
    根路径，返回 API 基本信息和健康状态。
    用于确认服务器是否在正常运行。
    """
    return {
        "api": "HireFlow",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
    }
