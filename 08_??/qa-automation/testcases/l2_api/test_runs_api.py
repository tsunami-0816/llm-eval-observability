# -*- coding: utf-8 -*-
"""L2: 评测跑批接口测试（创建/防重/详情/列表/异步终态对账）。"""
import pytest

from common.assert_util import assert_fail, assert_ok
from common.wait_util import wait_run_done


@pytest.fixture()
def make_run(run_api, make_prompt, make_dataset, mysql_conn, ch):
    """工厂：造一个 run（自带 prompt×2 + dataset），结束清理 MySQL 与 CH eval trace。"""
    created = []

    def _make(case_count=2, differ=True):
        a = make_prompt(version="vA", content="答案A:{{input}}" if differ else "相同:{{input}}")
        b = make_prompt(version="vB", content="答案B:{{input}}" if differ else "相同:{{input}}")
        cases = [{"input": f"问题{i}", "expected_output": "参考", "scoring_criteria": "准确"}
                 for i in range(case_count)]
        ds_id = make_dataset(cases=cases)
        data = assert_ok(run_api.create(ds_id, a["id"], b["id"]))
        created.append(data["run_id"])
        return {"run_id": data["run_id"], "dataset_id": ds_id,
                "prompt_a_id": a["id"], "prompt_b_id": b["id"]}

    yield _make
    if created:
        ids = ",".join(map(str, created))
        with mysql_conn.cursor() as cur:
            cur.execute(f"DELETE FROM eval_result WHERE run_id IN ({ids})")
            cur.execute(f"DELETE FROM eval_run WHERE id IN ({ids})")
    try:  # CH eval trace 清理（best-effort）
        ch.command("ALTER TABLE trace_records DELETE WHERE source = 'eval'",
                   settings={"mutations_sync": 1})
    except Exception as e:
        print(f"CH eval trace 清理失败（可忽略）: {e}")


@pytest.mark.l2
class TestRunsApi:
    @pytest.mark.p0
    def test_create_run_success(self, make_run, run_api):
        """正向：创建 run 返回 run_id + running，列表可见。"""
        info = make_run()
        runs = assert_ok(run_api.list())
        hit = [r for r in runs if r["id"] == info["run_id"]]
        assert hit, "新建 run 应出现在列表"
        assert hit[0]["status"] in ("running", "done")
        assert hit[0]["dataset_id"] == info["dataset_id"]

    @pytest.mark.p0
    def test_create_run_duplicate_409(self, make_run, run_api):
        """防重（任务拆解 M6-1）：同 dataset+a+b running 期间重发返回 409。"""
        info = make_run(case_count=50)  # 拉长 running 窗口
        resp = run_api.create(info["dataset_id"], info["prompt_a_id"], info["prompt_b_id"])
        assert_fail(resp, 409)

    def test_run_detail_not_found_404(self, run_api):
        """反向：查询不存在的 run 返回 404。"""
        assert_fail(run_api.detail(99999999), 404)

    @pytest.mark.p0
    def test_run_done_scores(self, make_run, run_api, mysql_conn):
        """正向+对账：run 到 done 后 mock judge 6:4，eval_result 行数==cases 数。"""
        info = make_run(case_count=3)
        data = wait_run_done(run_api, info["run_id"])
        assert data["status"] == "done"
        assert data["total_cases"] == 3
        assert data["score_a_avg"] == 6.0
        assert data["score_b_avg"] == 4.0
        assert len(data["results"]) == 3
        for r in data["results"]:
            assert r["score_a"] == 6.0 and r["score_b"] == 4.0
            assert r["judge_reason"]
        with mysql_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM eval_result WHERE run_id=%s", (info["run_id"],))
            assert cur.fetchone()[0] == 3
        # 列表态同步 done
        hit = [r for r in assert_ok(run_api.list()) if r["id"] == info["run_id"]]
        assert hit[0]["status"] == "done" and hit[0]["total_cases"] == 3

    def test_run_tie_when_same_prompt(self, make_run, run_api):
        """边界：A/B prompt 内容相同 → 输出相同 → judge 5:5 平局。"""
        info = make_run(case_count=2, differ=False)
        data = wait_run_done(run_api, info["run_id"])
        assert data["status"] == "done"
        assert data["score_a_avg"] == 5.0
        assert data["score_b_avg"] == 5.0
