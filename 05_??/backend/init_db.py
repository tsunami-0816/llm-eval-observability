"""初始化 MySQL 业务表 + ClickHouse trace 表。"""
import asyncio

from app.clickhouse_client import init_trace_table
from app.database import Base, engine
from app import models  # noqa: F401 — 必须导入，否则 metadata 为空


async def init_mysql():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ MySQL 业务表已建")


def init_clickhouse():
    try:
        init_trace_table()
        print("✅ ClickHouse trace_records 表已建")
    except Exception as e:
        print(f"⚠️  ClickHouse 初始化失败（可稍后重试）：{e}")


if __name__ == "__main__":
    asyncio.run(init_mysql())
    init_clickhouse()
