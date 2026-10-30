"""评测跑批：起 run → BackgroundTasks 执行 → 聚合结果。"""
import asyncio  # 修复-Q001: to_thread 避免同步 CH insert 阻塞事件循环
import time
import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import schemas
from app.clickhouse_client import get_clickhouse_client
from app.config import settings
from app.database import SessionLocal, get_db
from app.models import EvalCase, EvalResult, EvalRun, PromptVersion

router = APIRouter()


def _mock_llm_call(prompt_content: str, user_input: str) -> str:
    """# MOCK: replace with real OpenAI/DeepSeek chat completion call.
    当前用字符串替换代替真实 LLM 调用，因为无 API key。配 key 后改为 openai.ChatCompletion.create。"""
    return prompt_content.replace("{{input}}", user_input)


def _mock_judge(output_a: str, output_b: str) -> tuple[float, float, str]:
    """# MOCK: replace with real LLM-as-judge call.
    当前硬编码 6:4 平局，配 key 后改为调 judge 模型打分。"""
    if output_a == output_b:
        return 5.0, 5.0, "A/B 输出相同，平局"
    return 6.0, 4.0, "A 略优"


async def _run_eval(run_id: int):
    """后台执行评测。"""
    async with SessionLocal() as db:
        run = await db.get(EvalRun, run_id)
        if not run:
            return

        # 取 prompt 内容
        prompt_a = await db.get(PromptVersion, run.prompt_a_id)
        prompt_b = await db.get(PromptVersion, run.prompt_b_id)

        # 取 cases
        result = await db.execute(select(EvalCase).where(EvalCase.dataset_id == run.dataset_id))
        cases = result.scalars().all()
        run.total_cases = len(cases)

        score_a_sum = 0.0
        score_b_sum = 0.0
        trace_rows = []

        for case in cases:
            # Prompt A 调用（带计时，模拟真实 LLM 延迟）
            t0 = time.time()
            output_a = _mock_llm_call(prompt_a.content, case.input)
            latency_a = int((time.time() - t0) * 1000) + 50  # mock 延迟

            # Prompt B 调用
            t1 = time.time()
            output_b = _mock_llm_call(prompt_b.content, case.input)
            latency_b = int((time.time() - t1) * 1000) + 30

            score_a, score_b, reason = _mock_judge(output_a, output_b)
            score_a_sum += score_a
            score_b_sum += score_b

            db.add(EvalResult(
                run_id=run_id,
                case_id=case.id,
                score_a=score_a,
                score_b=score_b,
                judge_reason=reason,
            ))

            # 写 trace 到 ClickHouse（让看板数据和评测链路关联）
            now = datetime.utcnow()
            for output, latency, pv in [
                (output_a, latency_a, prompt_a),
                (output_b, latency_b, prompt_b),
            ]:
                prompt_tokens = len(pv.content) // 4
                completion_tokens = len(output) // 4
                trace_rows.append([
                    str(uuid.uuid4()), 1, pv.name, pv.content, output,
                    prompt_tokens, completion_tokens, 0.0001, latency,
                    "eval", "success", "", "", now,
                ])
        # 批量写 ClickHouse
        if trace_rows:
            try:
                client = get_clickhouse_client()
                columns = [
                    "trace_id", "project_id", "model", "prompt_text", "output_text",
                    "prompt_tokens", "completion_tokens", "cost_usd", "latency_ms",
                    "source", "status", "error_message", "parent_span_id", "created_time",
                ]
                # 修复-Q001: 同步 insert 放线程池，防止跑批期间阻塞事件循环导致全 API 卡死
                await asyncio.to_thread(
                    client.insert, "trace_records", trace_rows, column_names=columns)
                client.close()
            except Exception as e:
                print(f"⚠️  eval trace write failed: {e}")

        run.score_a_avg = round(score_a_sum / len(cases), 2) if cases else 0
        run.score_b_avg = round(score_b_sum / len(cases), 2) if cases else 0
        run.status = "done"
        run.finished_at = datetime.utcnow()
        await db.commit()


@router.post("/runs")
async def create_run(
    body: schemas.RunCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    # 防重：同 dataset+a+b 10 分钟内有 running 则拒绝
    result = await db.execute(
        select(EvalRun).where(
            EvalRun.dataset_id == body.dataset_id,
            EvalRun.prompt_a_id == body.prompt_a_id,
            EvalRun.prompt_b_id == body.prompt_b_id,
            EvalRun.status == "running",
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="已有同配置评测在跑")

    run = EvalRun(**body.model_dump())
    db.add(run)
    await db.commit()
    await db.refresh(run)

    background_tasks.add_task(_run_eval, run.id)
    return {"code": 0, "data": {"run_id": run.id, "status": "running"}, "message": "ok"}


@router.get("/runs")
async def list_runs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(EvalRun).order_by(EvalRun.id.desc()))
    runs = result.scalars().all()
    return {
        "code": 0,
        "data": [
            {
                "id": r.id,
                "dataset_id": r.dataset_id,
                "prompt_a_id": r.prompt_a_id,
                "prompt_b_id": r.prompt_b_id,
                "status": r.status,
                "score_a_avg": float(r.score_a_avg),
                "score_b_avg": float(r.score_b_avg),
                "total_cases": r.total_cases,
                "started_at": r.started_at.isoformat(),
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            }
            for r in runs
        ],
        "message": "ok",
    }


@router.get("/runs/{run_id}")
async def get_run(run_id: int, db: AsyncSession = Depends(get_db)):
    run = await db.get(EvalRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")

    result = await db.execute(select(EvalResult).where(EvalResult.run_id == run_id))
    results = result.scalars().all()

    return {
        "code": 0,
        "data": {
            "id": run.id,
            "status": run.status,
            "score_a_avg": float(run.score_a_avg),
            "score_b_avg": float(run.score_b_avg),
            "total_cases": run.total_cases,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "results": [
                {"case_id": r.case_id, "score_a": float(r.score_a),
                 "score_b": float(r.score_b), "judge_reason": r.judge_reason}
                for r in results
            ],
        },
        "message": "ok",
    }
