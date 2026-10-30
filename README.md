# llm-eval-observability

[![QA Automation CI](https://img.shields.io/badge/QA%20Automation%20CI-62%20passed-brightgreen)](.github/workflows/test.yml)

> 注：badge 为静态标识；GitHub Actions 实时 badge 在第 10.5 步推送远程后自动生效（工作流：`.github/workflows/test.yml`，push 到 main 自动跑 `pytest --collect-only` 用例收集检查）。

LLM 评测与可观测性平台（MVP）：Prompt 版本管理 / 评测集管理 / A-B 评测跑批（mock judge）/ SDK 一行接入 trace 上报 / ClickHouse 存储 / 看板聚合（延迟 P50/P99、成功率、成本、Token）。

## 架构

```
业务方 --(pip sdk, init_tracer)--> POST /api/traces --内存队列 0.5s 批量--> ClickHouse
前端 Vue3(5179) --axios--> FastAPI 后端(8086) --> MySQL(3310) 评测元数据
                                            \-> Redis(6381) 30s 看板缓存
```

- 后端：FastAPI + SQLAlchemy(async) + clickhouse-connect + redis，单 uvicorn 进程
- 前端：Vite + Vue3 + ElementPlus + ECharts（Dashboard / Prompt 管理 / 评测对比）
- SDK：`05_代码/sdk/llm_eval_sdk`，`init_tracer` 自动 hook openai，`@trace_call` 手动模式
- 中间件：docker-compose（MySQL 3310 / ClickHouse 8123+9000 / Redis 6381）

## 快速开始

```bash
# 1. 中间件
docker compose up -d

# 2. 后端（8086）
cd 05_代码/backend && pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8086

# 3. 前端（5179）
cd 05_代码/frontend && npm install && npm run dev
```

## 测试（第 8 步交付）

```bash
cd 08_测试/qa-automation
pip install -r requirements.txt
python -m pytest --tb=short -q        # 全量 63 用例（需本地中间件+后端运行）
python -m pytest -m p0 -q             # P0 冒烟子集 15 条
python benchmarks/m_bench.py          # M3/M4/M7/M8 基线 benchmark
python perf_test.py                   # 10/20/50 并发压测
```

- 测试框架：pytest 四层金字塔（L1 单元 26 / L2 接口 28 / L3 中间件 3 / L4 E2E 3）
- 报告：Allure（`reports/html`）、性能报告 `perf-report.md`、用例清单 `../全量测试用例清单.md`
- 基线指标验证：`../基线指标验证表.md`（M1~M8，6 条自动化全绿 + M7 实测绿 + M6 无 key 标注未验证风险）
