# -*- coding: utf-8 -*-
"""终态轮询工具：异步/执行类用例必须轮询到终态，禁止 sleep 固定时长后断言。"""
import time

import pytest

from common.assert_util import assert_ok


def wait_run_done(run_api, run_id: int, timeout: float = 60.0) -> dict:
    """轮询 run 到终态（done/failed），超时 fail。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        data = assert_ok(run_api.detail(run_id))
        if data["status"] in ("done", "failed"):
            return data
        time.sleep(0.3)
    pytest.fail(f"run {run_id} {timeout}s 内未到终态")


def wait_trace_in_ch(trace_api, trace_id: str, timeout: float = 10.0) -> dict:
    """轮询 ClickHouse flush（0.5s 一批）后 trace 可查。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = trace_api.get(trace_id)
        if resp.status_code == 200:
            return assert_ok(resp)
        time.sleep(0.4)
    pytest.fail(f"trace {trace_id} {timeout}s 内未落 ClickHouse")
