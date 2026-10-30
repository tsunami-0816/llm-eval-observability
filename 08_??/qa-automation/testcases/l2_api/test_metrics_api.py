# -*- coding: utf-8 -*-
"""L2: 看板聚合接口测试（字段齐全/range_days 边界/timeseries）。"""
import pytest

from api.eval_platform_api import make_trace
from common.assert_util import assert_ok
from common.wait_util import wait_trace_in_ch

SUMMARY_KEYS = {"calls", "tokens", "cost", "p50_ms", "p99_ms", "error_rate"}


@pytest.fixture()
def clear_metrics_cache(redis_conn):
    """metrics 接口有 30s Redis 缓存，用例前清掉避免读到旧快照。"""
    for key in redis_conn.scan_iter("cache:*"):
        redis_conn.delete(key)
    yield


@pytest.mark.l2
class TestMetricsApi:
    @pytest.mark.p0
    def test_summary_fields(self, metric_api, trace_api, clear_metrics_cache):
        """正向：上报 1 条 trace 后 summary 六字段齐全、无 NaN、calls>=1。"""
        rec = make_trace()
        assert_ok(trace_api.report([rec]))
        wait_trace_in_ch(trace_api, rec["trace_id"])
        data = assert_ok(metric_api.summary(range_days=1))
        assert set(data.keys()) == SUMMARY_KEYS
        assert data["calls"] >= 1
        assert data["tokens"] >= 0 and data["cost"] >= 0
        assert data["p50_ms"] >= 0 and data["p99_ms"] >= 0
        assert 0 <= data["error_rate"] <= 1

    def test_summary_range_days_zero(self, metric_api, clear_metrics_cache):
        """边界：range_days=0 → 空窗口，calls==0，聚合不出现 NaN（_safe 兜底）。"""
        data = assert_ok(metric_api.summary(range_days=0))
        assert set(data.keys()) == SUMMARY_KEYS
        assert data["calls"] == 0
        assert data["error_rate"] == 0

    def test_summary_range_days_negative(self, metric_api, clear_metrics_cache):
        """边界：range_days=-1 不应 500，按空窗口处理。"""
        data = assert_ok(metric_api.summary(range_days=-1))
        assert data["calls"] == 0

    @pytest.mark.p0
    def test_timeseries_positive(self, metric_api, trace_api, clear_metrics_cache):
        """正向：有数据时 timeseries 按日返回 date/p50/p99，p99>=p50。"""
        rec = make_trace(latency_ms=123)
        assert_ok(trace_api.report([rec]))
        wait_trace_in_ch(trace_api, rec["trace_id"])
        data = assert_ok(metric_api.timeseries(range_days=1))
        assert isinstance(data, list) and data
        item = data[-1]
        assert {"date", "p50", "p99"} <= set(item.keys())
        assert item["p50"] >= 0
        assert item["p99"] >= item["p50"]

    @pytest.mark.xfail(
        reason="metrics.py timeseries 忽略 metric 参数、写死 latency 序列（台账登记 P3）",
        strict=False)
    def test_timeseries_metric_param_honored(self, metric_api, clear_metrics_cache):
        """反向（已知缺陷）：metric=cost 应返回 cost 维度序列，当前被忽略写死 latency。"""
        data = assert_ok(metric_api.timeseries(metric="cost", range_days=1))
        assert data and "cost" in data[0]
