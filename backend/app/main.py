import sys
from pathlib import Path

# 将 backend 目录添加到 Python 路径
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import prescriptions, herbs, medics, search, knowledge_graph, knowledge_graph_v2, ai, sync, auth, admin
from app.core.config import settings

app = FastAPI(
    title="中医药知识图谱系统",
    description="基于 FastAPI + React + MySQL + Neo4j 的中医药智能知识管理系统",
    version="1.0.0"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 调试期间允许所有来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局异常处理
from fastapi import Request
from fastapi.responses import JSONResponse
import traceback

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理器，捕获所有未处理的异常"""
    # 记录错误日志
    error_detail = f"{type(exc).__name__}: {str(exc)}"
    traceback_str = traceback.format_exc()
    print(f"全局异常捕获: {error_detail}")
    print(f"请求路径: {request.url}")
    print(f"堆栈跟踪:\n{traceback_str}")
    
    # 返回统一的错误响应格式
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "服务器内部错误，请稍后重试",
                "detail": error_detail if settings.DEBUG else None
            }
        }
    )

# 注册路由
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(prescriptions.router, prefix="/api/prescriptions", tags=["prescriptions"])
app.include_router(herbs.router, prefix="/api/herbs", tags=["herbs"])
app.include_router(medics.router, prefix="/api/medics", tags=["medics"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(knowledge_graph.router, prefix="/api/knowledge-graph", tags=["knowledge-graph"])
app.include_router(knowledge_graph_v2.router, prefix="/api/knowledge-graph-v2", tags=["knowledge-graph-v2"])
app.include_router(ai.router, prefix="/api/ai", tags=["ai"])
app.include_router(sync.router, prefix="/api/sync", tags=["sync"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])

@app.get("/")
async def root():
    return {"message": "中医药知识图谱系统 API"}

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.getenv("PORT", 10000))
    print(f"启动FastAPI应用，端口: {port}")
    # 调试CORS配置
    try:
        if hasattr(app, 'user_middleware') and len(app.user_middleware) > 0:
            middleware = app.user_middleware[0]
            if hasattr(middleware, 'options'):
                print(f"允许的CORS来源: {middleware.options.get('allow_origins', '未设置')}")
    except Exception as e:
        print(f"读取CORS配置时出错: {e}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")