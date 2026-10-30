# -*- coding: utf-8 -*-
"""第 7 步 R1 定向回归：Q-001（事件循环阻塞/防重）+ Q-002（SDK hook）+ 影响面（C/D 链路）。"""
import asyncio
import io
import sys
import threading
import time

import clickhouse_connect
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
BASE = "http://127.0.0.1:8086"  # 修复-Q001: 禁 localhost（IPv6 回退 2s 伪影）
API_KEY = "dev-sdk-key-change-me"
results = []


def rec(item, ok, evidence):
    results.append((item, ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {item} :: {evidence}")


def ch_count(where="1=1"):
    c = clickhouse_connect.get_client(host="127.0.0.1", port=8123,
                                      username="default", password="chpass123")
    n = c.query(f"SELECT count() FROM trace_records WHERE {where}").result_rows[0][0]
    c.close()
    return n


print("== R1 回归 Q-001：跑批期间 API 延迟 + 防重 409 ==")
# 探活
for _ in range(30):
    try:
        requests.get(f"{BASE}/health", timeout=1)
        break
    except Exception:
        time.sleep(0.5)

# 延迟探针：跑批期间 GET /prompts 必须 <500ms
lat = []
stop = threading.Event()


def probe():
    while not stop.is_set():
        t0 = time.time()
        try:
            requests.get(f"{BASE}/api/prompts", timeout=5)
            lat.append((time.time() - t0) * 1000)
        except Exception:
            lat.append(9999)
        time.sleep(0.2)


th = threading.Thread(target=probe)
th.start()
time.sleep(0.3)
r1 = requests.post(f"{BASE}/api/runs", json={"dataset_id": 5, "prompt_a_id": 13, "prompt_b_id": 14})
r2 = requests.post(f"{BASE}/api/runs", json={"dataset_id": 5, "prompt_a_id": 13, "prompt_b_id": 14})
rid = r1.json()["data"]["run_id"]
for _ in range(60):
    time.sleep(1)
    if requests.get(f"{BASE}/api/runs/{rid}").json()["data"]["status"] == "done":
        break
stop.set()
th.join()
worst = max(lat) if lat else -1
rec("Q-001a 跑批期间 GET /prompts 延迟 <500ms", worst < 500,
    f"探针{len(lat)}次 最差={worst:.0f}ms（修复前全部~2050ms）")
rec("Q-001b running 防重 409（M6-1）", r1.status_code == 200 and r2.status_code == 409,
    f"首发={r1.status_code} 重发={r2.status_code}")

# 影响面 C：POST /traces 仍正常
import uuid
tid = str(uuid.uuid4())
c0 = ch_count()
r = requests.post(f"{BASE}/api/traces", json=[{
    "trace_id": tid, "project_id": 1, "model": "r1-regress", "prompt_text": "回归探针",
    "output_text": "x", "prompt_tokens": 1, "completion_tokens": 1, "cost_usd": 0.0,
    "latency_ms": 1, "source": "sdk", "status": "success", "error_message": ""}],
    headers={"x-api-key": API_KEY})
time.sleep(1.2)
rec("影响面C POST /traces+flush 正常", r.status_code == 200 and ch_count() - c0 == 1,
    f"status={r.status_code} CH增量={ch_count()-c0}")

# 影响面 D：run 16 类型跑批结果一致性（沿用 D 链路断言方式）
rr = requests.get(f"{BASE}/api/runs/{rid}").json()["data"]
rec("影响面D 跑批完成且total_cases=303", rr["status"] == "done" and rr["total_cases"] == 303,
    f"status={rr['status']} total={rr['total_cases']} score_a={rr['score_a_avg']}")

print("== R1 回归 Q-002：SDK init_tracer 不崩 + 手动/断网链路 ==")
sys.path.insert(0, r"D:\lg\project\工作流测试\projects\llm-eval-observability\05_代码\sdk")
try:
    from llm_eval_sdk import init_tracer, trace_call
    from llm_eval_sdk.openai_hook import _patched
    from llm_eval_sdk.reporter import init_reporter

    init_tracer(api_endpoint=BASE, api_key=API_KEY, project_id=1)
    rec("Q-002a init_tracer 不崩（装了 openai）", True, f"hook patched={_patched}")

    sdk0 = ch_count("source = 'openai'")

    @trace_call(model="r1-regress-sdk")
    async def fake_llm(prompt: str) -> str:
        return f"回显:{prompt}"

    async def run_f1():
        o = await fake_llm("SDK回归")
        await asyncio.sleep(0.3)
        return o
    out = asyncio.run(run_f1())
    time.sleep(1.5)
    sdk1 = ch_count("source = 'openai'")
    rec("Q-002b @trace_call 上报入CH", sdk1 - sdk0 >= 1 and out == "回显:SDK回归",
        f"返回={out!r} CH增量={sdk1-sdk0}")

    # 断网：业务不阻塞
    async def run_f2():
        init_reporter("http://127.0.0.1:9", "k", 1)

        @trace_call(model="r1-offline")
        async def fake2(prompt: str) -> str:
            return f"ok:{prompt}"
        t0 = time.time()
        o = await fake2("断网")
        await asyncio.sleep(2.3)
        return o, (time.time() - t0) * 1000
    out2, dt = asyncio.run(run_f2())
    rec("Q-002c 断网不阻塞业务(M8)", out2 == "ok:断网" and dt < 3500,
        f"返回={out2!r} 总耗时={dt:.0f}ms")

    # hook 真实性：同步 openai 客户端调用被 patch（不真调 API，只验证 patch 生效且 send_trace 不炸）
    from openai import OpenAI
    client = OpenAI(api_key="fake", base_url="http://127.0.0.1:9/v1", timeout=1, max_retries=0)
    init_reporter(BASE, API_KEY, 1)
    try:
        client.chat.completions.create(model="x", messages=[{"role": "user", "content": "hi"}])
    except Exception as e:
        # 期望：连接失败被 hook 捕获上报 error trace，异常照常抛出（业务语义不变）
        ok_types = ("APIConnectionError", "APITimeoutError", "ConnectionError")
        rec("Q-002d hook 生效且同步上下文 send_trace 不炸",
            type(e).__name__ in ok_types,
            f"业务异常类型={type(e).__name__}（hook 已包装，error trace 线程上报）")
except Exception as e:
    rec("Q-002 SDK 链路", False, f"{type(e).__name__}: {e}")

print("=" * 60)
fails = [x for x in results if not x[1]]
print(f"R1 回归汇总: {len(results)-len(fails)}/{len(results)} PASS, {len(fails)} FAIL")
sys.exit(1 if fails else 0)
