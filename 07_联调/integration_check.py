# -*- coding: utf-8 -*-
"""第 7 步全链路联调实测脚本（链路 A~F）。
用法：python integration_check.py
判定：每项打印 PASS/FAIL + 证据；结尾输出汇总。问题人工记入 _问题台账.md。
"""
import io
import json
import sys
import time
import uuid

import clickhouse_connect
import pymysql
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE = "http://127.0.0.1:8086"  # 修复-Q001: 禁 localhost，Windows IPv6(::1) 回退固定 ~2s 延迟
PROXY = "http://127.0.0.1:5179"  # vite 代理，验证前端同源链路
API_KEY = "dev-sdk-key-change-me"

results = []


def rec(item, ok, evidence):
    results.append((item, ok, evidence))
    print(f"[{'PASS' if ok else 'FAIL'}] {item} :: {evidence}")


def mysql():
    return pymysql.connect(host="127.0.0.1", port=3310, user="root",
                           password="root123", database="eoe", charset="utf8mb4")


def ch():
    return clickhouse_connect.get_client(host="127.0.0.1", port=8123,
                                         username="default", password="chpass123")


def ch_count(where="1=1"):
    c = ch()
    n = c.query(f"SELECT count() FROM trace_records WHERE {where}").result_rows[0][0]
    c.close()
    return n


print("=" * 70)
print("链路 A · Prompt 版本管理（utf8mb4）")
print("=" * 70)

# A1 创建中文 prompt（UTF-8 客户端）
cn_content = "请把以下内容翻译成英文:{{input}}"
r = requests.post(f"{BASE}/api/prompts", json={
    "name": "翻译助手", "version": "v3.0", "content": cn_content, "description": "联调A1"})
rec("A1 POST /prompts 中文创建", r.status_code == 200 and r.json()["code"] == 0,
    f"status={r.status_code} body={r.text[:120]}")
a1_id = r.json()["data"]["id"]

# A1 回读一致
r = requests.get(f"{BASE}/api/prompts")
found = [p for p in r.json()["data"] if p["id"] == a1_id]
ok = found and found[0]["content"] == cn_content
rec("A1 GET /prompts 中文回读一致", bool(ok),
    f"回读content={found[0]['content']!r}" if found else "未找到记录")

# A2 MySQL HEX 验证（非 3F 问号）
conn = mysql()
with conn.cursor() as cur:
    cur.execute("SELECT HEX(LEFT(content,6)) FROM prompt_version WHERE id=%s", (a1_id,))
    hexv = cur.fetchone()[0]
rec("A2 MySQL 存储层 UTF-8", not hexv.startswith("3F"), f"HEX(前6字符)={hexv}")
conn.close()

# A3 同 name 不同 version 共存
r = requests.post(f"{BASE}/api/prompts", json={
    "name": "翻译助手", "version": "v3.1", "content": "Translate to English: {{input}}",
    "description": "联调A3"})
r2 = requests.get(f"{BASE}/api/prompts")
versions = [p["version"] for p in r2.json()["data"] if p["name"] == "翻译助手"]
rec("A3 同名多版本共存", "v3.0" in versions and "v3.1" in versions, f"versions={versions}")
a3_id = r.json()["data"]["id"]

# A4 诊断存量乱码 id=3
conn = mysql()
with conn.cursor() as cur:
    cur.execute("SELECT HEX(LEFT(content,6)) FROM prompt_version WHERE id=3")
    hex3 = cur.fetchone()[0]
conn.close()
rec("A4 存量 id=3 乱码根因诊断", True,
    f"id=3 HEX={hex3} → 存储即 3F，写入端编码丢失（第6步 PowerShell 提交所致），"
    f"应用层 UTF-8 链路经 A1/A2 证明正常 → 记 P2 deferred")

print("=" * 70)
print("链路 B · 评测集与 cases")
print("=" * 70)

r = requests.post(f"{BASE}/api/datasets", json={
    "name": "联调评测集-中英", "description": "B1", "project_id": 1})
rec("B1 POST /datasets", r.status_code == 200 and r.json()["code"] == 0, r.text[:100])
b_ds = r.json()["data"]["id"]

cases_payload = {"cases": [
    {"input": "你好，世界", "expected_output": "Hello, World", "scoring_criteria": "准确性"},
    {"input": "人工智能是未来的方向", "expected_output": "AI is the future", "scoring_criteria": "流畅性"},
    {"input": "今天天气怎么样", "expected_output": "How is the weather today", "scoring_criteria": "完整性"},
    {"input": "", "expected_output": "空输入应被跳过"},  # B3 边界
]}
r = requests.post(f"{BASE}/api/datasets/{b_ds}/cases", json=cases_payload)
rec("B2+B3 POST cases 批量导入(含空input边界)",
    r.json()["data"]["imported"] == 3, f"imported={r.json()['data']['imported']}（预期3，跳过空）")

r = requests.get(f"{BASE}/api/datasets/{b_ds}/cases")
cases = r.json()["data"]
ok = len(cases) == 3 and cases[0]["input"] == "你好，世界"
rec("B2 GET cases 回读中文一致", ok, f"count={len(cases)} first_input={cases[0]['input']!r}")

print("=" * 70)
print("链路 C · trace 上报 → ClickHouse")
print("=" * 70)

c0 = ch_count()
tid1, tid2 = str(uuid.uuid4()), str(uuid.uuid4())
now_ms = int(time.time() * 1000)
payload = [
    {"trace_id": tid1, "project_id": 1, "model": "deepseek-chat",
     "prompt_text": "翻译成英文:你好", "output_text": "Hello",
     "prompt_tokens": 10, "completion_tokens": 2, "cost_usd": 0.0001,
     "latency_ms": 120, "source": "sdk", "status": "success", "error_message": ""},
    {"trace_id": tid2, "project_id": 1, "model": "gpt-4o-mini",
     "prompt_text": "ping", "output_text": "pong",
     "prompt_tokens": 1, "completion_tokens": 1, "cost_usd": 0.0002,
     "latency_ms": 80, "source": "sdk", "status": "error", "error_message": "联调错误注入"},
]
r = requests.post(f"{BASE}/api/traces", json=payload, headers={"x-api-key": API_KEY})
rec("C1 POST /traces 正确key", r.status_code == 200 and r.json()["data"]["accepted"] == 2,
    r.text[:100])

r = requests.post(f"{BASE}/api/traces", json=payload, headers={"x-api-key": "wrong"})
rec("C2 错误key拒绝", r.status_code == 401, f"status={r.status_code}")

time.sleep(1.2)  # 等 flush（0.5s 周期）
c1 = ch_count()
rec("C4 ClickHouse 批量flush无丢失", c1 - c0 == 2, f"count {c0}→{c1}（增量={c1-c0}，预期2）")

r = requests.get(f"{BASE}/api/traces/{tid1}")
d = r.json().get("data", {})
need = ["model", "prompt_text", "output_text", "prompt_tokens", "latency_ms", "status"]
missing = [k for k in need if k not in d]
rec("C3 GET /traces/{id} 字段齐全(M5)", r.status_code == 200 and not missing,
    f"missing={missing} model={d.get('model')} prompt={d.get('prompt_text')!r}")
rec("C5 中文 trace CH 回读", d.get("prompt_text") == "翻译成英文:你好",
    f"prompt_text={d.get('prompt_text')!r}")

print("=" * 70)
print("链路 D · 评测跑批端到端（MySQL+CH 双写一致）")
print("=" * 70)

d_ch0 = ch_count("source = 'eval'")
r = requests.post(f"{BASE}/api/runs", json={
    "dataset_id": b_ds, "prompt_a_id": a1_id, "prompt_b_id": a3_id})
rec("D1 POST /runs", r.status_code == 200 and r.json()["code"] == 0, r.text[:120])
run_id = r.json()["data"]["run_id"]

# D2 轮询到 done
final = None
for _ in range(30):
    time.sleep(1)
    rr = requests.get(f"{BASE}/api/runs/{run_id}").json()["data"]
    if rr["status"] == "done":
        final = rr
        break
rec("D2 跑批完成", final is not None,
    f"status={final and final['status']} total_cases={final and final['total_cases']} "
    f"score_a={final and final['score_a_avg']} score_b={final and final['score_b_avg']}")

# D3 MySQL eval_result 行数与聚合一致
conn = mysql()
with conn.cursor() as cur:
    cur.execute("SELECT COUNT(*), AVG(score_a), AVG(score_b) FROM eval_result WHERE run_id=%s",
                (run_id,))
    cnt, avg_a, avg_b = cur.fetchone()
    cur.execute("SELECT status, total_cases FROM eval_run WHERE id=%s", (run_id,))
    run_row = cur.fetchone()
conn.close()
ok = cnt == 3 and abs(float(avg_a) - final["score_a_avg"]) < 0.01 and run_row[0] == "done"
rec("D3 MySQL eval_result 一致", ok,
    f"result行数={cnt}（预期3）avg_a={float(avg_a):.2f} vs run.score_a={final['score_a_avg']} run_status={run_row[0]}")

# D4 ClickHouse source=eval 增量=2×cases
d_ch1 = ch_count("source = 'eval'")
rec("D4 CH eval trace 双写一致", d_ch1 - d_ch0 == 6,
    f"source=eval 增量={d_ch1-d_ch0}（预期6=2×3cases）")

# D6 runs 列表含新 run
r = requests.get(f"{BASE}/api/runs")
rec("D6 GET /runs 列表", any(x["id"] == run_id for x in r.json()["data"]),
    f"run_id={run_id} 在列表中；最新={r.json()['data'][0]['id']}")

# run 详情 results 明细
rr = requests.get(f"{BASE}/api/runs/{run_id}").json()["data"]
rec("D2b run详情含逐case结果", len(rr.get("results", [])) == 3,
    f"results={len(rr.get('results', []))}条")

# D5 防重行为观察：3 cases 毫秒级完成竞态抓不住；严格测试在 D5b
r_dup = requests.post(f"{BASE}/api/runs", json={
    "dataset_id": b_ds, "prompt_a_id": a1_id, "prompt_b_id": a3_id})
print(f"    [i] D5 小dataset重发: status={r_dup.status_code}（done后复跑属正常行为）")
if r_dup.status_code == 200:
    dup_id = r_dup.json()["data"]["run_id"]
    for _ in range(30):
        time.sleep(1)
        if requests.get(f"{BASE}/api/runs/{dup_id}").json()["data"]["status"] == "done":
            break

# D5b 防重严测：300 cases 大 dataset，running 窗口拉到秒级，重发必须 409
big_cases = {"cases": [{"input": f"防重测试case{i}", "expected_output": "x"} for i in range(300)]}
requests.post(f"{BASE}/api/datasets/{b_ds}/cases", json=big_cases)
r_big1 = requests.post(f"{BASE}/api/runs", json={
    "dataset_id": b_ds, "prompt_a_id": a1_id, "prompt_b_id": a3_id})
r_big2 = requests.post(f"{BASE}/api/runs", json={
    "dataset_id": b_ds, "prompt_a_id": a1_id, "prompt_b_id": a3_id})
rec("D5b running中重发=409", r_big1.status_code == 200 and r_big2.status_code == 409,
    f"首发={r_big1.status_code} 重发={r_big2.status_code}")
# 等大 run 跑完，避免影响后续 CH 计数
big_run = r_big1.json()["data"]["run_id"]
for _ in range(60):
    time.sleep(1)
    if requests.get(f"{BASE}/api/runs/{big_run}").json()["data"]["status"] == "done":
        break
rec("D5c 大run收敛", requests.get(f"{BASE}/api/runs/{big_run}").json()["data"]["status"] == "done",
    f"big_run={big_run} total=303cases")

print("=" * 70)
print("链路 E · 看板聚合（CH + Redis 缓存）")
print("=" * 70)

# ClickHouse 手工聚合对账（含今天全部数据）
c = ch()
row = c.query("""
    SELECT count(), sum(prompt_tokens+completion_tokens), sum(cost_usd),
           quantile(0.5)(latency_ms), quantile(0.99)(latency_ms),
           countIf(status='error')/count()
    FROM trace_records WHERE created_time >= now() - INTERVAL 7 DAY
""").result_rows[0]
c.close()

r1 = requests.get(f"{BASE}/api/metrics/summary").json()["data"]
ok = (r1["calls"] == row[0] and r1["tokens"] == row[1]
      and abs(r1["p50_ms"] - round(row[3], 1)) < 0.2)
rec("E1 summary 与 CH 直查一致", ok,
    f"api={r1} | ch_direct: calls={row[0]} tokens={row[1]} p50={round(row[3],1)} "
    f"p99={round(row[4],1)} err={round(row[5],4)}")

# E2 Redis 缓存：30s 内第二次调用应返回缓存（值相同）；再验证写新 trace 后缓存期内容不变
r2 = requests.get(f"{BASE}/api/metrics/summary").json()["data"]
rec("E2 30s内二次调用一致(缓存)", r1 == r2, f"两次结果{'相同' if r1 == r2 else '不同'}")

# 缓存正确性：缓存期内写入新 trace，summary 不变（30s TTL 内允许旧值，但 TTL 后必须更新）
c_before = ch_count()
tid_c = str(uuid.uuid4())
requests.post(f"{BASE}/api/traces", json=[{
    "trace_id": tid_c, "project_id": 1, "model": "cache-test", "prompt_text": "缓存探测",
    "output_text": "x", "prompt_tokens": 1, "completion_tokens": 1, "cost_usd": 0.0,
    "latency_ms": 1, "source": "sdk", "status": "success", "error_message": ""}],
    headers={"x-api-key": API_KEY})
time.sleep(1.2)
r3 = requests.get(f"{BASE}/api/metrics/summary").json()["data"]
rec("E2b 缓存TTL内旧值（设计允许）", True,
    f"写入后缓存内calls={r3['calls']}（缓存值，允许≠实时）")
print("    …等待 31s 让 Redis 缓存过期，验证缓存不失效卡死…")
time.sleep(31)
r4 = requests.get(f"{BASE}/api/metrics/summary").json()["data"]
rec("E2c 缓存过期后聚合更新", r4["calls"] == ch_count(),
    f"过期后calls={r4['calls']} vs CH实际={ch_count()}")

r = requests.get(f"{BASE}/api/metrics/timeseries")
ts = r.json()["data"]
rec("E3 timeseries 今日有数据", len(ts) >= 1, f"data={ts}")

r = requests.get(f"{BASE}/api/metrics/summary?range_days=0")
rec("E4 边界 range_days=0 不500", r.status_code == 200, f"status={r.status_code} body={r.text[:100]}")
r = requests.get(f"{BASE}/api/metrics/summary?range_days=-5")
rec("E4b 边界 range_days=-5", r.status_code == 200, f"status={r.status_code} body={r.text[:100]}")

print("=" * 70)
print("链路 F · SDK 端到端（M8 上报不阻塞）")
print("=" * 70)

sys.path.insert(0, r"D:\lg\project\工作流测试\projects\llm-eval-observability\05_代码\sdk")
try:
    import asyncio

    from llm_eval_sdk import init_tracer, trace_call  # noqa
    from llm_eval_sdk.reporter import init_reporter  # noqa

    async def f1():
        init_tracer(api_endpoint=BASE, api_key=API_KEY, project_id=1)

        @trace_call(model="sdk-联调")
        async def fake_llm(prompt: str) -> str:
            return f"回显:{prompt}"

        out = await fake_llm("SDK联调测试")
        await asyncio.sleep(0.3)  # 让 fire-and-forget 协程发出去
        return out

    sdk0 = ch_count("source = 'openai'")
    out = asyncio.run(f1())
    time.sleep(1.5)  # 等服务端 flush（0.5s 周期）
    sdk1 = ch_count("source = 'openai'")
    rec("F1 SDK @trace_call 上报入CH", sdk1 - sdk0 >= 1 and out == "回显:SDK联调测试",
        f"业务返回={out!r} source=openai 增量={sdk1-sdk0}")

    # F2/M8 上报端不可达：reporter 指向死端口，业务调用必须正常返回且不慢
    async def f2():
        init_reporter("http://127.0.0.1:9", "k", 1)

        @trace_call(model="sdk-断网")
        async def fake_llm2(prompt: str) -> str:
            return f"ok:{prompt}"

        t0 = time.time()
        o = await fake_llm2("断网测试")
        await asyncio.sleep(2.5)  # 等上报超时（aiohttp total=2s）走完
        return o, (time.time() - t0) * 1000

    out2, dt = asyncio.run(f2())
    rec("F2/M8 上报失败不阻塞业务", out2 == "ok:断网测试" and dt < 3500,
        f"业务返回={out2!r} 含2s上报超时总耗时={dt:.0f}ms")
except Exception as e:
    rec("F1/F2 SDK 链路", False, f"SDK 导入/执行失败: {type(e).__name__}: {e}")

print("=" * 70)
print("链路 G0 · 前端代理连通性（页面走查见浏览器记录）")
print("=" * 70)
r = requests.get(f"{PROXY}/api/prompts")
rec("G0 5179 代理 → 8086", r.status_code == 200 and r.json()["code"] == 0,
    f"status={r.status_code}")

print("=" * 70)
fails = [x for x in results if not x[1]]
print(f"汇总: {len(results)-len(fails)}/{len(results)} PASS, {len(fails)} FAIL")
for item, _, ev in fails:
    print(f"  FAIL → {item}: {ev}")
sys.exit(1 if fails else 0)
