# -*- coding: utf-8 -*-
"""L1: 成本核算 calc_cost 单元测试（M6 成本准确性的纯函数基础）。"""
import pytest

from llm_eval_sdk.cost import COST_TABLE, calc_cost


@pytest.mark.l1
class TestCalcCost:
    def test_gpt4o_known_model_exact(self):
        """已知 model 按定价表精确计算：1K input + 1K output = 0.0025+0.01。"""
        assert calc_cost("gpt-4o", 1000, 1000) == pytest.approx(0.0125, abs=1e-6)

    def test_deepseek_known_model(self):
        """DeepSeek 模型走自己的定价档。"""
        # 0.00014*1 + 0.00028*2 = 0.0007
        assert calc_cost("deepseek-chat", 1000, 2000) == pytest.approx(0.0007, abs=1e-6)

    def test_unknown_model_fallback(self):
        """未知 model 按 _default（gpt-4o-mini 档）兜底，不抛异常。"""
        assert calc_cost("some-new-model", 1000, 1000) == pytest.approx(
            (1000 / 1000) * COST_TABLE["_default"]["input"]
            + (1000 / 1000) * COST_TABLE["_default"]["output"], abs=1e-6)

    def test_zero_tokens_zero_cost(self):
        """边界：0 token 成本为 0。"""
        assert calc_cost("gpt-4o", 0, 0) == 0

    def test_large_tokens_precision(self):
        """大 token 量精度：1M input gpt-4o = 2.5 USD，round 6 位。"""
        assert calc_cost("gpt-4o", 1_000_000, 0) == pytest.approx(2.5, abs=1e-6)

    def test_cost_table_no_negative_price(self):
        """定价表完整性：所有档位单价非负且有 input/output 两键。"""
        for model, price in COST_TABLE.items():
            assert price["input"] >= 0 and price["output"] >= 0, model
