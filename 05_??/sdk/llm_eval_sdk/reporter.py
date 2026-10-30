"""异步上报：aiohttp POST /api/traces，失败静默（M8）。"""
import asyncio
import logging
import uuid
from typing import Any

import aiohttp

logger = logging.getLogger("llm_eval_sdk")

_reporter: dict[str, Any] = {}


def init_reporter(api_endpoint: str, api_key: str, project_id: int = 1):
    _reporter["endpoint"] = api_endpoint.rstrip("/") + "/api/traces"
    _reporter["api_key"] = api_key
    _reporter["project_id"] = project_id


async def _post(record: dict):
    try:
        timeout = aiohttp.ClientTimeout(total=2)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                _reporter["endpoint"],
                json=[record],
                headers={"X-API-Key": _reporter["api_key"], "Content-Type": "application/json"},
            ) as resp:
                await resp.read()
    except Exception as e:
        # M8：上报失败不抛业务异常
        logger.debug(f"trace upload failed silently: {e}")


def send_trace(record: dict):
    """异步发送，fire-and-forget。无 running loop（同步上下文）时退化为 daemon 线程。"""
    if "endpoint" not in _reporter:
        return
    record.setdefault("trace_id", str(uuid.uuid4()))
    record.setdefault("project_id", _reporter["project_id"])
    # 修复-Q002: 同步上下文（如被 hook 的同步 openai 调用）没有 running loop，
    # asyncio.create_task 会 RuntimeError 反噬业务调用（违反 M8），改为 daemon 线程发送。
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_post(record))
    except RuntimeError:
        import threading
        threading.Thread(target=asyncio.run, args=(_post(record),), daemon=True).start()
