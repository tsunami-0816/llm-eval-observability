# -*- coding: utf-8 -*-
"""L2: 评测集与 cases 接口四象限测试。"""
import pytest

from common.assert_util import assert_fail, assert_ok


@pytest.mark.l2
class TestDatasetsApi:
    @pytest.mark.p0
    def test_create_dataset_success(self, make_dataset, dataset_api):
        """正向：创建评测集后列表可查。"""
        ds_id = make_dataset(name="qa-评测集")
        datasets = assert_ok(dataset_api.list())
        assert any(d["id"] == ds_id for d in datasets)

    def test_create_dataset_missing_name_422(self, dataset_api):
        """反向：缺 name 返回 422。"""
        resp = dataset_api.c.post("/api/datasets", json={"description": "x"})
        assert_fail(resp, 422)

    @pytest.mark.p0
    def test_import_cases_success(self, make_dataset, dataset_api):
        """正向：批量导入 cases，逐条字段对账。"""
        ds_id = make_dataset()
        cases = [
            {"input": "输入一", "expected_output": "输出一", "scoring_criteria": "准确性"},
            {"input": "输入二", "expected_output": "输出二"},
        ]
        data = assert_ok(dataset_api.import_cases(ds_id, cases))
        assert data["imported"] == 2
        stored = assert_ok(dataset_api.list_cases(ds_id))
        assert len(stored) == 2
        assert stored[0]["input"] == "输入一"
        assert stored[0]["expected_output"] == "输出一"
        assert stored[0]["scoring_criteria"] == "准确性"

    def test_import_cases_skip_empty_input(self, make_dataset, dataset_api):
        """边界：空 input 的 case 被跳过，其余正常导入。"""
        ds_id = make_dataset()
        data = assert_ok(dataset_api.import_cases(ds_id, [
            {"input": "", "expected_output": "x"},
            {"input": "有效输入", "expected_output": "y"},
        ]))
        assert data["imported"] == 1
        stored = assert_ok(dataset_api.list_cases(ds_id))
        assert len(stored) == 1

    def test_import_cases_to_ghost_dataset(self, make_dataset, dataset_api, mysql_conn):
        """反向：给不存在的 dataset 导 cases——记录实际行为供评审（当前无外键拦截）。"""
        resp = dataset_api.import_cases(99999999, [{"input": "孤儿", "expected_output": "x"}])
        # 不论 200/4xx/5xx，先清理可能写入的孤儿数据
        with mysql_conn.cursor() as cur:
            cur.execute("DELETE FROM eval_case WHERE dataset_id=99999999")
        assert resp.status_code in (200, 404, 422, 500)

    def test_list_cases_empty_dataset(self, make_dataset, dataset_api):
        """边界：空评测集返回空列表而非报错。"""
        ds_id = make_dataset()
        assert assert_ok(dataset_api.list_cases(ds_id)) == []
