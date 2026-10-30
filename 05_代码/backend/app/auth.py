"""全局 API Key 鉴权依赖（修复-SEC003：全部业务接口统一校验 X-API-Key）。"""
from fastapi import Header, HTTPException

from app.config import settings


async def verify_api_key(x_api_key: str = Header(None)):
    # sdk_api_key 未配置时 fail-closed：任何请求都 401，不放行
    if not settings.sdk_api_key or x_api_key != settings.sdk_api_key:
        raise HTTPException(status_code=401, detail="invalid api key")
