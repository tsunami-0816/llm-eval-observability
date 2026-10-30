# -*- coding: utf-8 -*-
"""L2: Trace 上报/查询接口四象限测试。"""
import pytest
import requests

from api.eval_platform_api import make_trace
from common.assert_util import assert_fail, assert_ok
from common.request_util import ApiClient
from common.wait_util import wait_trace_in_ch


@pytest.mark.l2
class TestTracesApi:
    @pytest.mark.p0
    def test_report_traces_accepted(self, trace_api):
        """正向：上报 2 条合法 trace，返回 accepted=2。"""
        data = assert_ok(trace_api.report([make_trace(), make_trace()]))
        assert data["accepted"] == 2

    def test_report_wrong_key_401(self, cfg):
        """越权：错误 X-API-Key 上报返回 401。"""
        bad_client = ApiClient(cfg["base_url"], "wrong-key-qa")
        resp = bad_client.post("/api/traces", json=[make_trace()])
        assert_fail(resp, 401)

    def test_report_missing_key_401(self, cfg):
        """越权：不带 X-API-Key 上报返回 401。"""
        resp = requests.post(
            f"{cfg['base_url']}/api/traces", json=[make_trace()], timeout=10)
        assert resp.status_code == 401

    def test_report_prompt_too_long_422(self, trace_api):
        """边界：prompt_text 超 100000 字符返回 422。"""
        resp = trace_api.report([make_trace(prompt="长" * 100001)])
        assert_fail(resp, 422)

    def test_get_trace_not_found_404(self, trace_api):
        """反向：查询不存在的 trace_id 返回 404。"""
        assert_fail(trace_api.get("qa-not-exist-00000000"), 404)

    @pytest.mark.p0
    def test_trace_flush_roundtrip(self, trace_api):
        """正向：上报后 0.5s 批量落 CH，按 trace_id 回读字段原样。"""
        rec = make_trace(model="qa-回读模型", source="deepseek", latency_ms=321,
                         prompt="回读中文输入", output="回读中文输出")
        assert_ok(trace_api.report([rec]))
        data = wait_trace_in_ch(trace_api, rec["trace_id"])
        assert data["model"] == "qa-回读模型"
        assert data["source"] == "deepseek"
        assert data["latency_ms"] == 321
        assert data["prompt_text"] == "回读中文输入"
        assert data["output_text"] == "回读中文输出"
        assert data["status"] == "success"
