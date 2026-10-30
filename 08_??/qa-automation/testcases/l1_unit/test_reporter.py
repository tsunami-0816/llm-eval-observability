# -*- coding: utf-8 -*-
"""L1: reporter 上报单元测试 + M8 上报不阻塞业务基线。"""
import asyncio
import time

import pytest

import llm_eval_sdk.reporter as reporter_module
from llm_eval_sdk.reporter import init_reporter, send_trace


@pytest.fixture(autouse=True)
def reset_reporter():
    """每条用例前清空全局 reporter 配置，保证用例独立。"""
    reporter_module._reporter.clear()
    yield
    reporter_module._reporter.clear()


def _wait_sent(sent: list, timeout: float = 2.0):
    """同步上下文走 daemon 线程发送，轮询等送达，禁止裸断言竞态。"""
    deadline = time.time() + timeout
    while time.time() < deadline and not sent:
        time.sleep(0.02)


@pytest.mark.l1
class TestReporter:
    def test_send_without_init_silent(self):
        """未 init 时 send_trace 静默返回，不抛异常。"""
        send_trace({"model": "m"})  # 不抛即通过

    def test_trace_id_auto_filled(self, monkeypatch):
        """record 缺 trace_id 时自动补 uuid。"""
        init_reporter("http://127.0.0.1:9", "k")
        sent = []

        async def fake_post(record):
            sent.append(record)

        monkeypatch.setattr(reporter_module, "_post", fake_post)
        send_trace({"model": "m"})
        _wait_sent(sent)
        assert sent, "应有 1 条 record 进入发送管线"
        assert sent[0]["trace_id"], "trace_id 应被自动补齐"

    def test_project_id_default_1(self, monkeypatch):
        """project_id 默认取 init 时的值。"""
        init_reporter("http://127.0.0.1:9", "k", project_id=7)
        sent = []

        async def fake_post(record):
            sent.append(record)

        monkeypatch.setattr(reporter_module, "_post", fake_post)
        send_trace({"model": "m"})
        _wait_sent(sent)
        assert sent and sent[0]["project_id"] == 7

    def test_sync_context_no_loop_fallback(self, monkeypatch):
        """同步上下文（无 running loop）不 RuntimeError，退化 daemon 线程发送。"""
        init_reporter("http://127.0.0.1:9", "k")
        done = asyncio.Event()
        sent = []

        async def fake_post(record):
            sent.append(record)
            done.set()

        monkeypatch.setattr(reporter_module, "_post", fake_post)
        # 主线程无 running loop，老实现此处必炸 RuntimeError（Q-002）
        send_trace({"model": "m"})
        # 等 daemon 线程把 record 送达
        _wait_sent(sent)
        assert sent, "daemon 线程兜底应最终送达"

    async def test_async_context_uses_create_task(self, monkeypatch):
        """异步上下文走 loop.create_task，不额外起线程。"""
        init_reporter("http://127.0.0.1:9", "k")
        sent = []

        async def fake_post(record):
            sent.append(record)

        monkeypatch.setattr(reporter_module, "_post", fake_post)
        send_trace({"model": "m"})
        await asyncio.sleep(0.05)
        assert len(sent) == 1

    @pytest.mark.p0
    def test_m8_report_failure_not_blocking_business(self):
        """M8 基线：上报端不可达时，send_trace 100 次平均劣化 ≤ 5ms/次。"""
        # 端口 9 是 discard 协议保留端口，本机无监听，连接必失败
        init_reporter("http://127.0.0.1:9", "k")
        n = 100
        t0 = time.perf_counter()
        for _ in range(n):
            send_trace({"model": "m", "prompt_text": "p", "output_text": "o"})
        avg_ms = (time.perf_counter() - t0) / n * 1000
        assert avg_ms <= 5, f"断网场景 send_trace 平均 {avg_ms:.3f}ms 超 5ms"
