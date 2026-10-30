"""FastAPI 主入口。"""
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth import verify_api_key
from app.config import settings
from app.routers import datasets, metrics, prompts, runs, traces

app = FastAPI(title="LLM Eval Observability", version="0.1.0")

# 修复-SEC004: CORS 收紧为本地前端源；无 Cookie 场景，credentials 关闭
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5179",
        "http://127.0.0.1:5179",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 修复-SEC003: 全部业务接口统一挂 API Key 鉴权（/health 除外，供探活）
_auth = [Depends(verify_api_key)]
app.include_router(traces.router, prefix="/api", tags=["traces"], dependencies=_auth)
app.include_router(prompts.router, prefix="/api", tags=["prompts"], dependencies=_auth)
app.include_router(datasets.router, prefix="/api", tags=["datasets"], dependencies=_auth)
app.include_router(runs.router, prefix="/api", tags=["runs"], dependencies=_auth)
app.include_router(metrics.router, prefix="/api", tags=["metrics"], dependencies=_auth)


@app.get("/health")
async def health():
    return {"code": 0, "data": {"status": "up", "env": settings.app_env}, "message": "ok"}
