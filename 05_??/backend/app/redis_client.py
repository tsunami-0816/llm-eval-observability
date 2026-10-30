"""Redis 连接 + 30s 缓存装饰器。"""
import json
from functools import wraps

import redis

from app.config import settings

redis_client = redis.Redis(
    host=settings.redis_host,
    port=settings.redis_port,
    db=settings.redis_db,
    decode_responses=True,
)


def cache_ttl(ttl_seconds: int = 30):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            key = f"cache:{func.__name__}:{args}:{kwargs}"
            try:
                cached = redis_client.get(key)
                if cached:
                    return json.loads(cached)
            except redis.RedisError:
                pass  # 缓存挂了不阻塞业务

            result = await func(*args, **kwargs)
            try:
                redis_client.setex(key, ttl_seconds, json.dumps(result, default=str))
            except redis.RedisError:
                pass
            return result

        return wrapper

    return decorator
