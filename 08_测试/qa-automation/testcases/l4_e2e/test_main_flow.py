# -*- coding: utf-8 -*-
"""L4: E2E 主链路（仅 P0 主路径）。"""
import asyncio
import time
import uuid

import pytest

from api.eval_platform_api import make_trace
from common.assert_util import assert_ok
from common.wait_util import wait_run_done, wait_trace_in_ch


@pytest.mark.l4
class TestMainFlow:
    @pytest.mark.p0
    def test_eval_main_flow(self, run_api, metric_api, make_prompt, make_dataset,
                            mysql_conn, redis_conn):
        """主链路：建 prompt×2 → 建数据集导 case → 起 run → done 6:4 → 看板 summary 有数。"""
        a = make_prompt(version="vA", content="主链路A:{{input}}")
        b = make_prompt(version="vB", content="主链路B:{{input}}")
        ds_id = make_dataset(cases=[
            {"input": "主链路问题1", "expected_output": "参考1", "scoring_criteria": "准确"},
            {"input": "主链路问题2", "expected_output": "参考2", "scoring_criteria": "准确"}])
        run_id = assert_ok(run_api.create(ds_id, a["id"], b["id"]))["run_id"]
        try:
            detail = wait_run_done(run_api, run_id)
            assert detail["status"] == "done"
            assert detail["total_cases"] == 2
            assert detail["score_a_avg"] == 6.0
            assert detail["score_b_avg"] == 4.0
            assert len(detail["results"]) == 2
            # 看板聚合：跑批的 4 条 eval trace（2 cases × A/B）在 done 前已写 CH
            for key in redis_conn.scan_iter("cache:*"):
                redis_conn.delete(key)
            summary = assert_ok(metric_api.summary(range_days=1))
            assert summary["calls"] >= 4
        finally:
            with mysql_conn.cursor() as cur:
                cur.execute("DELETE FROM eval_result WHERE run_id=%s", (run_id,))
                cur.execute("DELETE FROM eval_run WHERE id=%s", (run_id,))

    @pytest.mark.p0
    def test_sdk_trace_call_full_link(self, cfg, ch):
        """SDK 全链路：init_tracer + @trace_call → 上报 → CH 可查（M5 手动模式）。"""
        from llm_eval_sdk import init_tracer, trace_call

        model = f"qa-sdk-{uuid.uuid4().hex[:8]}"
        init_tracer(cfg["base_url"], cfg["sdk_api_key"])

        @trace_call(model=model)
        async def fake_llm(prompt: str):
            await asyncio.sleep(0.01)
            return "SDK 全链路输出"

        async def drive():
            out = await fake_llm("SDK 全链路输入")
            await asyncio.sleep(1.0)  # 等 fire-and-forget 上报任务发完
            return out

        assert asyncio.run(drive()) == "SDK 全链路输出"

        deadline = time.time() + 15
        row = None
        while time.time() < deadline:
            r = ch.query(
                "SELECT prompt_text, output_text, status, source FROM trace_records "
                "WHERE model = %(m)s LIMIT 1", parameters={"m": model})
            if r.row_count:
                row = r.first_item
                break
            time.sleep(0.5)
        try:
            assert row, "SDK 上报的 trace 15s 内未落 ClickHouse"
            assert row["prompt_text"] == "SDK 全链路输入"
            assert row["output_text"] == "SDK 全链路输出"
            assert row["status"] == "success"
            assert row["source"] == "openai"
        finally:
            try:
                ch.command(f"ALTER TABLE trace_records DELETE WHERE model = '{model}'",
                           settings={"mutations_sync": 1})
            except Exception:
                pass

    @pytest.mark.p0
    def test_multi_source_traces(self, trace_api, ch):
        """M5 多来源：openai/deepseek/langchain 各上报一条，CH 回读 source/model 字段齐全。"""
        recs = [make_trace(source=s, model=f"qa-m5-{s}")
                for s in ("openai", "deepseek", "langchain")]
        assert_ok(trace_api.report(recs))
        try:
            for rec in recs:
                data = wait_trace_in_ch(trace_api, rec["trace_id"])
                assert data["source"] == rec["source"]
                assert data["model"] == rec["model"]
                for field in ("prompt_text", "output_text", "prompt_tokens",
                              "completion_tokens", "cost_usd", "latency_ms"):
                    assert field in data, f"缺字段 {field}"
        finally:
            ids = ",".join(f"'{r['trace_id']}'" for r in recs)
            try:
                ch.command(f"ALTER TABLE trace_records DELETE WHERE trace_id IN ({ids})",
                           settings={"mutations_sync": 1})
            except Exception:
                pass
