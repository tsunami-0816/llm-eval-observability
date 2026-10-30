# -*- coding: utf-8 -*-
"""统一返回体断言：成功 code==0 返回 data；失败返回完整 body。"""


def assert_ok(resp, expect_status: int = 200):
    """断言 HTTP 状态 + 业务 code==0，返回 data 供后续字段断言。"""
    assert resp.status_code == expect_status, f"HTTP {resp.status_code}: {resp.text[:500]}"
    body = resp.json()
    assert body.get("code") == 0, f"业务 code != 0: {body}"
    return body["data"]


def assert_fail(resp, expect_status: int):
    """断言反向用例的 HTTP 状态码，返回 body。"""
    assert resp.status_code == expect_status, (
        f"期望 HTTP {expect_status}，实际 {resp.status_code}: {resp.text[:500]}")
    return resp.json()
