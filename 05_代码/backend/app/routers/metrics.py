"""看板聚合查询。"""
import math

from fastapi import APIRouter

from app.clickhouse_client import get_clickhouse_client
from app.redis_client import cache_ttl

router = APIRouter()


def _safe(v, default=0):
    """ClickHouse 空表聚合返回 NaN，转成默认值。"""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return default
    return v


@router.get("/metrics/summary")
@cache_ttl(30)
async def summary(range_days: int = 7):
    client = get_clickhouse_client()
    result = client.query(
        """
        SELECT
            count() AS calls,
            sum(prompt_tokens + completion_tokens) AS tokens,
            sum(cost_usd) AS cost,
            quantile(0.5)(latency_ms) AS p50,
            quantile(0.99)(latency_ms) AS p99,
            countIf(status = 'error') / count() AS error_rate
        FROM trace_records
        WHERE created_time >= now() - INTERVAL %(days)s DAY
        """,
        parameters={"days": range_days},
    )
    client.close()
    row = result.first_item
    return {
        "code": 0,
        "data": {
            "calls": _safe(row["calls"]),
            "tokens": _safe(row["tokens"]),
            "cost": round(_safe(row["cost"]), 4),
            "p50_ms": round(_safe(row["p50"]), 1),
            "p99_ms": round(_safe(row["p99"]), 1),
            "error_rate": round(_safe(row["error_rate"]), 4),
        },
        "message": "ok",
    }


@router.get("/metrics/timeseries")
@cache_ttl(30)
async def timeseries(metric: str = "latency", range_days: int = 7):
    client = get_clickhouse_client()
    result = client.query(
        """
        SELECT
            toDate(created_time) AS date,
            quantile(0.5)(latency_ms) AS p50,
            quantile(0.99)(latency_ms) AS p99
        FROM trace_records
        WHERE created_time >= now() - INTERVAL %(days)s DAY
        GROUP BY date
        ORDER BY date
        """,
        parameters={"days": range_days},
    )
    client.close()
    return {
        "code": 0,
        "data": [
            {"date": str(row["date"]), "p50": round(_safe(row["p50"]), 1), "p99": round(_safe(row["p99"]), 1)}
            for row in result.named_results()
        ],
        "message": "ok",
    }
