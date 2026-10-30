"""trace 上报接收 + 查询。"""
import asyncio
from datetime import datetime

from fastapi import APIRouter, HTTPException

from app import schemas
from app.clickhouse_client import get_clickhouse_client

router = APIRouter()

# 内存批量写队列
_trace_buffer: list[dict] = []
_buffer_lock = asyncio.Lock()
_FLUSH_SIZE = 200
_FLUSH_INTERVAL = 0.5  # 秒


async def flush_buffer():
    """后台协程：攒够一批或超时就批量写 ClickHouse。"""
    global _trace_buffer
    while True:
        await asyncio.sleep(_FLUSH_INTERVAL)
        async with _buffer_lock:
            if not _trace_buffer:
                continue
            batch = _trace_buffer[:]
            _trace_buffer = []
        try:
            client = get_clickhouse_client()
            columns = [
                "trace_id", "project_id", "model", "prompt_text", "output_text",
                "prompt_tokens", "completion_tokens", "cost_usd", "latency_ms",
                "source", "status", "error_message", "parent_span_id", "created_time",
            ]
            rows = [
                [
                    r["trace_id"], r["project_id"], r["model"], r["prompt_text"],
                    r["output_text"], r["prompt_tokens"], r["completion_tokens"],
                    r["cost_usd"], r["latency_ms"], r["source"], r["status"],
                    r["error_message"], "", datetime.utcnow(),
                ]
                for r in batch
            ]
            # 修复-Q001: 同根因，flush 的同步 insert 也放线程池
            await asyncio.to_thread(
                client.insert, "trace_records", rows, column_names=columns)
            client.close()
        except Exception as e:
            # 写失败丢弃（M8：不阻塞接收端）
            print(f"⚠️  ClickHouse batch write failed, dropped {len(batch)} traces: {e}")


@router.on_event("startup")
async def startup():
    asyncio.create_task(flush_buffer())


@router.post("/traces")
async def receive_traces(records: list[schemas.TraceRecordIn]):
    # 鉴权由 main.py 路由级依赖 verify_api_key 统一完成（修复-SEC003）
    async with _buffer_lock:
        for r in records:
            _trace_buffer.append(r.model_dump())
    return {"code": 0, "data": {"accepted": len(records)}, "message": "ok"}


@router.get("/traces/{trace_id}")
async def get_trace(trace_id: str):
    client = get_clickhouse_client()
    result = client.query(
        "SELECT * FROM trace_records WHERE trace_id = %(tid)s LIMIT 1",
        parameters={"tid": trace_id},
    )
    client.close()
    if not result.row_count:
        raise HTTPException(status_code=404, detail="trace not found")
    row = result.first_item
    return {"code": 0, "data": row, "message": "ok"}
