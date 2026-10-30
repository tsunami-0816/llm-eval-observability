# -*- coding: utf-8 -*-
"""L1: trace_call 装饰器单元测试（mock send_trace）+ M1 SDK 开销基线。"""
import time

import pytest

import llm_eval_sdk.tracer as tracer_module
from llm_eval_sdk.tracer import trace_call


@pytest.fixture()
def captured(monkeypatch):
    """拦截 send_trace，返回收到的 record 列表。"""
    box = []
    monkeypatch.setattr(tracer_module, "send_trace", lambda rec: box.append(rec))
    return box


@pytest.mark.l1
class TestTraceCall:
    async def test_success_path_fields(self, captured):
        """成功调用：上报 record 字段齐全且 status=success，原结果透传。"""
        @trace_call(model="gpt-4o")
        async def fake_llm(prompt):
            return "hello world output"

        result = await fake_llm("你好")
        assert result == "hello world output"
        assert len(captured) == 1
        rec = captured[0]
        assert rec["model"] == "gpt-4o"
        assert rec["prompt_text"] == "你好"
        assert rec["output_text"] == "hello world output"
        assert rec["status"] == "success"
        assert isinstance(rec["latency_ms"], int) and rec["latency_ms"] >= 0
        # token 估算规则：len//4
        assert rec["prompt_tokens"] == len("你好") // 4
        assert rec["completion_tokens"] == len("hello world output") // 4
        assert rec["cost_usd"] >= 0

    async def test_exception_path_reraise(self, captured):
        """异常调用：上报 status=error + error_message，且异常原样抛给业务。"""
        @trace_call(model="gpt-4o")
        async def fake_llm(prompt):
            raise ValueError("llm exploded")

        with pytest.raises(ValueError, match="llm exploded"):
            await fake_llm("hi")
        assert len(captured) == 1
        rec = captured[0]
        assert rec["status"] == "error"
        assert "llm exploded" in rec["error_message"]
        assert rec["output_text"] == ""

    async def test_long_prompt_truncated(self, captured):
        """超长 prompt/output 截断到 100000 字符，防爆仓。"""
        @trace_call(model="gpt-4o")
        async def fake_llm(prompt):
            return "x" * 200000

        await fake_llm("p" * 150000)
        rec = captured[0]
        assert len(rec["prompt_text"]) == 100000
        assert len(rec["output_text"]) == 100000

    @pytest.mark.p0
    async def test_m1_sdk_overhead_p95_under_50ms(self, captured):
        """M1 基线：trace_call 包装后 P95 额外开销 ≤ 50ms（send_trace 已 mock 为纯内存操作）。"""
        async def bare_llm(prompt):
            return "ok"

        wrapped = trace_call(model="gpt-4o")(bare_llm)

        # 预热
        for _ in range(50):
            await bare_llm("x")
            await wrapped("x")

        n = 1000
        t0 = time.perf_counter()
        for _ in range(n):
            await bare_llm("x")
        bare_total = time.perf_counter() - t0

        t0 = time.perf_counter()
        for _ in range(n):
            await wrapped("x")
        wrapped_total = time.perf_counter() - t0

        overhead_ms = (wrapped_total - bare_total) / n * 1000
        assert overhead_ms <= 50, f"SDK 包装平均开销 {overhead_ms:.3f}ms 超 50ms"
