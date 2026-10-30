# -*- coding: utf-8 -*-
"""8.5.1 Python 轻量压测：10/20/50 并发 × 10s，输出 avg RT / P95 RT / TPS / 错误率。

压测目标（不依赖外部 LLM）：
- 读接口：GET /api/metrics/summary（走 30s Redis 缓存，代表看板读路径）
- 写接口：POST /api/traces（X-API-Key，代表 SDK 上报写路径，M2 对账依据）
运行：python perf_test.py
"""
import json
import statistics
import threading
import time
import uuid

import requests

BASE_URL = "http://127.0.0.1:8086"
API_KEY = "dev-sdk-key-change-me"
DURATION_S = 10
CONCURRENCY_LEVELS = [10, 20, 50]


def make_trace():
    return {
        "trace_id": str(uuid.uuid4()), "project_id": 1, "model": "perf-bench",
        "prompt_text": "perf 压测 prompt", "output_text": "perf 压测 output",
        "prompt_tokens": 10, "completion_tokens": 10, "cost_usd": 0.0001,
        "latency_ms": 100, "source": "perf", "status": "success", "error_message": "",
    }


def worker_read(stop_at, results):
    s = requests.Session()
    while time.time() < stop_at:
        t0 = time.perf_counter()
        try:
            r = s.get(f"{BASE_URL}/api/metrics/summary", params={"range_days": 7}, timeout=10)
            ok = r.status_code == 200
        except Exception:
            ok = False
        results.append(((time.perf_counter() - t0) * 1000, ok))


def worker_write(stop_at, results):
    s = requests.Session()
    s.headers["X-API-Key"] = API_KEY
    while time.time() < stop_at:
        body = [make_trace() for _ in range(10)]  # 每请求 10 条，贴近 SDK 批量上报
        t0 = time.perf_counter()
        try:
            r = s.post(f"{BASE_URL}/api/traces", json=body, timeout=10)
            ok = r.status_code == 200
        except Exception:
            ok = False
        results.append(((time.perf_counter() - t0) * 1000, ok, len(body)))


def run_level(name, worker, concurrency):
    results = []
    stop_at = time.time() + DURATION_S
    threads = [threading.Thread(target=worker, args=(stop_at, results)) for _ in range(concurrency)]
    t0 = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.time() - t0
    lats = [r[0] for r in results]
    ok_count = sum(1 for r in results if r[1])
    lats.sort()
    p95 = lats[int(len(lats) * 0.95) - 1] if lats else 0
    avg = statistics.mean(lats) if lats else 0
    tps = ok_count / elapsed
    err = (1 - ok_count / len(results)) * 100 if results else 100
    row = {
        "场景": name, "并发": concurrency, "请求数": len(results),
        "平均RT_ms": round(avg, 1), "P95_RT_ms": round(p95, 1),
        "TPS": round(tps, 1), "错误率%": round(err, 2),
    }
    if name.startswith("写"):
        row["写入条数"] = sum(r[2] for r in results if r[1])
        row["条/秒"] = round(row["写入条数"] / elapsed, 1)
    return row


def main():
    rows = []
    for c in CONCURRENCY_LEVELS:
        print(f"读接口 summary 并发 {c} × {DURATION_S}s ...", flush=True)
        rows.append(run_level("读 summary", worker_read, c))
    for c in CONCURRENCY_LEVELS:
        print(f"写接口 traces 并发 {c} × {DURATION_S}s ...", flush=True)
        rows.append(run_level("写 traces", worker_write, c))
    print("\n" + json.dumps(rows, ensure_ascii=False, indent=1))
    with open("perf_results.json", "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    print("已写 perf_results.json；CH 清理：DELETE WHERE source='perf' 或 model='perf-bench'")


if __name__ == "__main__":
    main()
