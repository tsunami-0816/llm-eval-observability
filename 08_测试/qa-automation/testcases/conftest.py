# -*- coding: utf-8 -*-
"""pytest fixture：配置/客户端/中间件连接/数据工厂（自造自清）/终态等待。"""
import os
import sys
import time
import uuid

import pytest

# 让 testcases 能 import common / api / sdk / backend app
QA_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PROJ_ROOT = os.path.abspath(os.path.join(QA_ROOT, "..", ".."))
for p in [QA_ROOT,
          os.path.join(PROJ_ROOT, "05_代码", "sdk"),
          os.path.join(PROJ_ROOT, "05_代码", "backend")]:
    if p not in sys.path:
        sys.path.insert(0, p)

import clickhouse_connect  # noqa: E402
import pymysql  # noqa: E402
import redis  # noqa: E402

from api.eval_platform_api import (DatasetApi, MetricApi, PromptApi,  # noqa: E402
                                   RunApi, TraceApi)
from common.assert_util import assert_ok  # noqa: E402
from common.request_util import ApiClient, load_config  # noqa: E402


@pytest.fixture(scope="session")
def cfg() -> dict:
    return load_config()


@pytest.fixture(scope="session")
def api(cfg) -> ApiClient:
    return ApiClient(cfg["base_url"], cfg["sdk_api_key"])


@pytest.fixture(scope="session")
def prompt_api(api):
    return PromptApi(api)


@pytest.fixture(scope="session")
def dataset_api(api):
    return DatasetApi(api)


@pytest.fixture(scope="session")
def run_api(api):
    return RunApi(api)


@pytest.fixture(scope="session")
def trace_api(api):
    return TraceApi(api)


@pytest.fixture(scope="session")
def metric_api(api):
    return MetricApi(api)


@pytest.fixture()
def mysql_conn(cfg):
    conn = pymysql.connect(**cfg["mysql"], charset="utf8mb4", autocommit=True)
    yield conn
    conn.close()


@pytest.fixture()
def ch(cfg):
    client = clickhouse_connect.get_client(**cfg["clickhouse"])
    yield client
    client.close()


@pytest.fixture()
def redis_conn(cfg):
    yield redis.Redis(**cfg["redis"], decode_responses=True)


def uniq(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


@pytest.fixture()
def make_prompt(prompt_api, mysql_conn):
    """工厂：创建一个 prompt 版本，用例结束 SQL 清理。"""
    created = []

    def _make(name=None, version="v1", content="请翻译:{{input}}", description="qa"):
        name = name or uniq("qa-prompt")
        data = assert_ok(prompt_api.create(name, version, content, description))
        created.append(data["id"])
        return data

    yield _make
    if created:
        with mysql_conn.cursor() as cur:
            cur.execute(f"DELETE FROM prompt_version WHERE id IN ({','.join(map(str, created))})")


@pytest.fixture()
def make_dataset(dataset_api, mysql_conn):
    """工厂：创建评测集（可带 cases），用例结束 SQL 清理。"""
    created = []

    def _make(name=None, cases: list[dict] | None = None):
        name = name or uniq("qa-ds")
        data = assert_ok(dataset_api.create(name, "qa 自造数据"))
        ds_id = data["id"]
        created.append(ds_id)
        if cases:
            assert_ok(dataset_api.import_cases(ds_id, cases))
        return ds_id

    yield _make
    if created:
        ids = ",".join(map(str, created))
        with mysql_conn.cursor() as cur:
            cur.execute(f"DELETE FROM eval_case WHERE dataset_id IN ({ids})")
            cur.execute(f"DELETE FROM eval_dataset WHERE id IN ({ids})")


# 终态轮询工具统一放 common.wait_util，此处 re-export 兼容
from common.wait_util import wait_run_done, wait_trace_in_ch  # noqa: F401,E402
