# -*- coding: utf-8 -*-
"""L3: 中间件集成测试。

降级说明（写进测试报告）：按 8.0 应使用 testcontainers 起临时容器，
但本机 16G 内存、docker-compose 三容器（MySQL/ClickHouse/Redis）已常驻占资源，
再开临时容器有 OOM 与启动过慢风险，故降级为「L2 接口 + 直连 docker-compose 中间件对账」。
覆盖关键链路：MySQL/CH 双写对账、Redis 缓存生效与失效、CH 直写直读。
"""
import datetime
import uuid

import pytest

from common.assert_util import assert_ok
from common.wait_util import wait_run_done, wait_trace_in_ch

CH_COLUMNS = [
    "trace_id", "project_id", "model", "prompt_text", "output_text",
    "prompt_tokens", "completion_tokens", "cost_usd", "latency_ms",
    "source", "status", "error_message", "parent_span_id", "created_time",
]


def _cleanup_run(mysql_conn, ch, run_id: int):
    with mysql_conn.cursor() as cur:
        cur.execute("DELETE FROM eval_result WHERE run_id=%s", (run_id,))
        cur.execute("DELETE FROM eval_run WHERE id=%s", (run_id,))
    try:
        ch.command("ALTER TABLE trace_records DELETE WHERE source = 'eval'",
                   settings={"mutations_sync": 1})
    except Exception as e:
        print(f"CH 清理失败（可忽略）: {e}")


@pytest.mark.l3
class TestMySQLClickHouseDoubleWrite:
    def test_eval_result_and_ch_trace_counts(self, run_api, make_prompt, make_dataset,
                                             mysql_conn, ch):
        """双写对账：3 cases 跑批 → MySQL eval_result 3 行 + CH source='eval' 6 行（A/B 各 1）。"""
        a = make_prompt(version="vA", content="对账A:{{input}}")
        b = make_prompt(version="vB", content="对账B:{{input}}")
        ds_id = make_dataset(cases=[
            {"input": f"对账问题{i}", "expected_output": "参考", "scoring_criteria": "准确"}
            for i in range(3)])
        before = ch.query(
            "SELECT count() AS c FROM trace_records WHERE source='eval'").first_item["c"]
        run_id = assert_ok(run_api.create(ds_id, a["id"], b["id"]))["run_id"]
        try:
            data = wait_run_done(run_api, run_id)
            assert data["status"] == "done"
            with mysql_conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM eval_result WHERE run_id=%s", (run_id,))
                assert cur.fetchone()[0] == 3
            after = ch.query(
                "SELECT count() AS c FROM trace_records WHERE source='eval'").first_item["c"]
            assert after - before == 6
        finally:
            _cleanup_run(mysql_conn, ch, run_id)


@pytest.mark.l3
class TestRedisCache:
    def test_cache_populate_and_invalidate(self, metric_api, trace_api, redis_conn):
        """缓存生效与失效：summary 写缓存（TTL≤30s）、缓存期返回旧快照、删 key 后重算。"""
        for key in redis_conn.scan_iter("cache:*"):
            redis_conn.delete(key)
        first = assert_ok(metric_api.summary(range_days=3))
        keys = list(redis_conn.scan_iter("cache:summary*"))
        assert keys, "summary 应写 Redis 缓存 key"
        ttl = redis_conn.ttl(keys[0])
        assert 0 < ttl <= 30

        # 缓存期内插入新 trace，再查仍是旧值（命中缓存）
        from api.eval_platform_api import make_trace
        rec = make_trace()
        assert_ok(trace_api.report([rec]))
        wait_trace_in_ch(trace_api, rec["trace_id"])
        second = assert_ok(metric_api.summary(range_days=3))
        assert second["calls"] == first["calls"], "30s 缓存期内应返回旧快照"

        # 模拟缓存失效（直删 key）后重新计算
        for key in redis_conn.scan_iter("cache:*"):
            redis_conn.delete(key)
        third = assert_ok(metric_api.summary(range_days=3))
        assert third["calls"] == first["calls"] + 1


@pytest.mark.l3
class TestClickHouseDirect:
    def test_insert_query_delete_roundtrip(self, ch):
        """CH 直连：写入中文→回读原样→mutation 删除后查无此行。"""
        tid = f"qa-ch-{uuid.uuid4().hex[:12]}"
        ch.insert("trace_records", [[
            tid, 1, "qa-直写模型", "中文提示词直写", "中文输出直写",
            10, 20, 0.001, 99, "qa", "success", "", "",
            datetime.datetime.utcnow(),
        ]], column_names=CH_COLUMNS)
        try:
            row = ch.query(
                "SELECT prompt_text, output_text FROM trace_records "
                "WHERE trace_id = %(tid)s LIMIT 1",
                parameters={"tid": tid}).first_item
            assert row["prompt_text"] == "中文提示词直写"
            assert row["output_text"] == "中文输出直写"
        finally:
            ch.command(f"ALTER TABLE trace_records DELETE WHERE trace_id = '{tid}'",
                       settings={"mutations_sync": 1})
        gone = ch.query("SELECT count() AS c FROM trace_records WHERE trace_id = %(tid)s",
                        parameters={"tid": tid}).first_item["c"]
        assert gone == 0
