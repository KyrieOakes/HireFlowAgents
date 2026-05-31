"""
app/main.py
============
FastAPI 应用入口文件。

这是 HireFlow 后端服务的启动文件。
FastAPI 是一个现代 Python Web 框架，用于构建高性能的 REST API。
运行方式: uvicorn app.main:app --reload
"""

from fastapi import FastAPI

# 创建 FastAPI 应用实例
# FastAPI() 会初始化一个全新的 Web 应用对象
# title 参数设置 API 文档的标题
# description 参数设置 API 文档的描述文字
app = FastAPI(
    title="HireFlow API",
    description="HireFlow: 基于 LangGraph 的多 Agent 招聘筛选与面试辅助系统",
    version="0.1.0",
)


# --- 根路径: 健康检查 ---
# @app.get("/") 是一个装饰器，告诉 FastAPI 当用户访问根路径 "/" 时执行下面的函数
# 这个方法用于检查服务器是否在正常运行
@app.get("/")
async def root():
    """
    根路径，返回 API 基本信息。

    返回:
        dict: 包含 API 名称和版本的字典
    """
    # 返回一个 JSON 格式的字典，FastAPI 会自动转换为 HTTP 响应
    return {"api": "HireFlow", "version": "0.1.0", "status": "running"}
