"""ClickHouse 连接（clickhouse-connect HTTP 接口）。"""
import clickhouse_connect

from app.config import settings


def get_clickhouse_client():
    return clickhouse_connect.get_client(
        host=settings.clickhouse_host,
        port=settings.clickhouse_http_port,
        username=settings.clickhouse_user,
        password=settings.clickhouse_password,
    )


TRACE_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS trace_records (
    trace_id String,
    project_id UInt32,
    model String,
    prompt_text String CODEC(ZSTD(3)),
    output_text String CODEC(ZSTD(3)),
    prompt_tokens UInt32,
    completion_tokens UInt32,
    cost_usd Float64,
    latency_ms UInt32,
    source String,
    status String,
    error_message String DEFAULT '',
    parent_span_id String DEFAULT '',
    created_time DateTime
)
ENGINE = MergeTree
PARTITION BY toYYYYMMDD(created_time)
ORDER BY (project_id, created_time)
TTL created_time + INTERVAL 90 DAY
"""


def init_trace_table():
    client = get_clickhouse_client()
    client.command(TRACE_TABLE_DDL)
    client.close()
