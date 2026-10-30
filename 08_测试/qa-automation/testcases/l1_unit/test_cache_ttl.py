# -*- coding: utf-8 -*-
"""L1: cache_ttl 缓存装饰器单元测试（mock redis，不碰真实中间件）。"""
import pytest

import app.redis_client as redis_module
from app.redis_client import cache_ttl


class FakeRedis:
    """dict 版假 redis：可切故障模式模拟 RedisError。"""

    def __init__(self):
        self.store = {}
        self.broken = False

    def get(self, key):
        if self.broken:
            import redis as real_redis
            raise real_redis.RedisError("boom")
        return self.store.get(key)

    def setex(self, key, ttl, value):
        if self.broken:
            import redis as real_redis
            raise real_redis.RedisError("boom")
        self.store[key] = value


@pytest.fixture()
def fake_redis(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(redis_module, "redis_client", fake)
    return fake


@pytest.mark.l1
class TestCacheTtl:
    async def test_miss_then_hit(self, fake_redis):
        """首次回源写缓存，第二次直接命中不回源。"""
        calls = []

        @cache_ttl(30)
        async def query(x):
            calls.append(x)
            return {"x": x}

        r1 = await query(1)
        r2 = await query(1)
        assert r1 == r2 == {"x": 1}
        assert calls == [1], "第二次应命中缓存不再回源"

    async def test_different_args_separate_cache(self, fake_redis):
        """不同入参缓存 key 不同，互不污染。"""
        @cache_ttl(30)
        async def query(x):
            return {"x": x}

        await query(1)
        await query(2)
        assert len(fake_redis.store) == 2

    async def test_redis_down_not_blocking(self, fake_redis):
        """Redis 故障时读写都静默跳过，业务照常返回。"""
        fake_redis.broken = True

        @cache_ttl(30)
        async def query(x):
            return {"x": x}

        assert await query(1) == {"x": 1}
        assert await query(1) == {"x": 1}

    async def test_cache_key_contains_func_name(self, fake_redis):
        """缓存 key 带函数名，防跨函数串数据。"""
        @cache_ttl(30)
        async def summary(x):
            return {"x": x}

        await summary(9)
        key = next(iter(fake_redis.store))
        assert key.startswith("cache:summary:")
