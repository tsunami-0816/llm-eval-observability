# -*- coding: utf-8 -*-
"""8.1.5 基线指标 benchmark：M3 / M4 / M7(接口层) / M8 实测值。

直接运行：python benchmarks/m_bench.py
- M7：1 万条种子 → /api/metrics/summary P95（目标 ≤500ms）
- M3：目标 100 万条（灌数软上限 300s，不足则按实际条数写诚实边界）→ summary P95（目标 ≤1s）
- M4：100 case 评测集跑批计时（目标 ≤60s，mock judge）
- M8：上报端不可达时 send_trace ×100 平均劣化（目标 ≤5ms）
跑完自动清理灌入数据（CH mutation 同步等待 + MySQL 删除）。
"""
import datetime
import os
import random
import statistics
import sys
import time

QA_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PROJ_ROOT = os.path.abspath(os.path.join(QA_ROOT, "..", ".."))
sys.path.insert(0, QA_ROOT)
sys.path.insert(0, os.path.join(PROJ_ROOT, "05_代码", "sdk"))

import clickhouse_connect  # noqa: E402
import pymysql  # noqa: E402
import redis  # noqa: E402

from api.eval_platform_api import PromptApi, DatasetApi, RunApi  # noqa: E402
from common.request_util import ApiClient, load_config  # noqa: E402
from common.assert_util import assert_ok  # noqa: E402
from common.wait_util import wait_run_done  # noqa: E402

cfg = load_config()
api = ApiClient(cfg["base_url"], cfg["sdk_api_key"])
ch = clickhouse_connect.get_client(**cfg["clickhouse"])
rds = redis.Redis(**cfg["redis"], decode_responses=True)

CH_COLUMNS = [
    "trace_id", "project_id", "model", "prompt_text", "output_text",
    "prompt_tokens", "completion_tokens", "cost_usd", "latency_ms",
    "source", "status", "error_message", "parent_span_id", "created_time",
]
BASE_URL = cfg["base_url"]


def clear_cache():
    for k in rds.scan_iter("cache:*"):
        rds.delete(k)


def seed(model: str, n: int, batch: int = 20000, time_budget: float = 300.0) -> int:
    """灌 n 条 trace（created_time 落在近 6 天内，确保进 7 天窗口），返回实际灌入数。"""
    import uuid
    inserted = 0
    t0 = time.time()
    while inserted < n and time.time() - t0 < time_budget:
        rows = []
        now = datetime.datetime.utcnow()
        for _ in range(min(batch, n - inserted)):
            lat = random.randint(10, 2000)
            status = "error" if random.random() < 0.05 else "success"
            created = now - datetime.timedelta(seconds=random.randint(0, 6 * 86400))
            rows.append([
                str(uuid.uuid4()), 1, model, "bench prompt 压测提示词", "bench output 压测输出",
                random.randint(10, 500), random.randint(10, 500), 0.0001, lat,
                "bench", status, "", "", created,
            ])
        ch.insert("trace_records", rows, column_names=CH_COLUMNS)
        inserted += len(rows)
        print(f"  灌数进度 {model}: {inserted}/{n}（{time.time() - t0:.0f}s）", flush=True)
    return inserted


def measure_summary_p95(rounds: int = 30) -> tuple[float, float]:
    """清缓存后测 summary P95，返回 (P95 ms, 均值 ms)。"""
    import requests
    lat_ms = []
    for _ in range(rounds):
        clear_cache()  # 绕过 30s 缓存，测真实 CH 聚合耗时
        t0 = time.perf_counter()
        resp = requests.get(f"{BASE_URL}/api/metrics/summary", params={"range_days": 7}, timeout=30)
        assert resp.status_code == 200, resp.text[:200]
        lat_ms.append((time.perf_counter() - t0) * 1000)
    lat_ms.sort()
    p95 = lat_ms[int(len(lat_ms) * 0.95) - 1]
    return p95, statistics.mean(lat_ms)


def cleanup_model(model: str):
    ch.command(f"ALTER TABLE trace_records DELETE WHERE model = '{model}'",
               settings={"mutations_sync": 1})


def bench_m7():
    print("== M7（接口层）：1 万条种子，summary P95 目标 ≤500ms ==", flush=True)
    n = seed("m7-bench", 10000)
    clear_cache()
    p95, avg = measure_summary_p95()
    cleanup_model("m7-bench")
    print(f"M7-API: 种子 {n} 条，summary P95={p95:.1f}ms avg={avg:.1f}ms -> "
          f"{'PASS' if p95 <= 500 else 'FAIL'}", flush=True)
    return {"seed": n, "p95": round(p95, 1), "avg": round(avg, 1), "pass": p95 <= 500}


def bench_m3():
    print("== M3：目标 100 万条，summary P95 目标 ≤1000ms ==", flush=True)
    n = seed("m3-bench", 1_000_000, time_budget=300.0)
    clear_cache()
    p95, avg = measure_summary_p95()
    cleanup_model("m3-bench")
    honest = "" if n >= 1_000_000 else f"（诚实边界：300s 预算内仅灌入 {n} 条，未达 100 万）"
    ok = p95 <= 1000
    print(f"M3: 实际 {n} 条{honest}，summary P95={p95:.1f}ms avg={avg:.1f}ms -> "
          f"{'PASS' if ok else 'FAIL'}", flush=True)
    return {"seed": n, "p95": round(p95, 1), "avg": round(avg, 1), "pass": ok, "honest": honest}


def bench_m4():
    print("== M4：100 case 评测跑批，目标 ≤60s ==", flush=True)
    prompt_api, ds_api, run_api = PromptApi(api), DatasetApi(api), RunApi(api)
    a = assert_ok(prompt_api.create("m4-bench-a", "v1", "M4基准A:{{input}}", "bench"))
    b = assert_ok(prompt_api.create("m4-bench-b", "v1", "M4基准B:{{input}}", "bench"))
    ds = assert_ok(ds_api.create("m4-bench-ds", "bench"))
    ds_id = ds["id"]
    cases = [{"input": f"M4问题{i}", "expected_output": "参考", "scoring_criteria": "准确"}
             for i in range(100)]
    assert_ok(ds_api.import_cases(ds_id, cases))
    run_id = assert_ok(run_api.create(ds_id, a["id"], b["id"]))["run_id"]
    t0 = time.time()
    detail = wait_run_done(run_api, run_id, timeout=120)
    elapsed = time.time() - t0
    assert detail["status"] == "done" and detail["total_cases"] == 100
    # 清理
    mysql = pymysql.connect(**cfg["mysql"], charset="utf8mb4", autocommit=True)
    with mysql.cursor() as cur:
        cur.execute("DELETE FROM eval_result WHERE run_id=%s", (run_id,))
        cur.execute("DELETE FROM eval_run WHERE id=%s", (run_id,))
        cur.execute("DELETE FROM eval_case WHERE dataset_id=%s", (ds_id,))
        cur.execute("DELETE FROM eval_dataset WHERE id=%s", (ds_id,))
        cur.execute("DELETE FROM prompt_version WHERE id IN (%s,%s)", (a["id"], b["id"]))
    mysql.close()
    try:
        ch.command("ALTER TABLE trace_records DELETE WHERE source = 'eval'",
                   settings={"mutations_sync": 1})
    except Exception as e:
        print(f"  CH eval 清理失败（可忽略）: {e}")
    ok = elapsed <= 60
    print(f"M4: 100 case 跑批 {elapsed:.1f}s -> {'PASS' if ok else 'FAIL'}", flush=True)
    return {"elapsed_s": round(elapsed, 1), "pass": ok}


def bench_m8():
    print("== M8：上报端不可达，send_trace ×100 平均劣化目标 ≤5ms ==", flush=True)
    import llm_eval_sdk.reporter as reporter
    from llm_eval_sdk.reporter import init_reporter, send_trace
    reporter._reporter.clear()
    init_reporter("http://127.0.0.1:9", "k")  # 端口 9 无监听，连接必失败
    n = 100
    t0 = time.perf_counter()
    for _ in range(n):
        send_trace({"model": "m", "prompt_text": "p", "output_text": "o"})
    avg_ms = (time.perf_counter() - t0) / n * 1000
    reporter._reporter.clear()
    ok = avg_ms <= 5
    print(f"M8: 平均劣化 {avg_ms:.3f}ms/次 -> {'PASS' if ok else 'FAIL'}", flush=True)
    return {"avg_ms": round(avg_ms, 3), "pass": ok}


if __name__ == "__main__":
    results = {"M7": bench_m7(), "M4": bench_m4(), "M8": bench_m8()}
    results["M3"] = bench_m3()  # 大灌数放最后，避免影响前面计时
    print("\n==== 汇总 ====")
    for k, v in results.items():
        print(k, v)
    clear_cache()
    ch.close()
