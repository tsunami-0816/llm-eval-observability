# -*- coding: utf-8 -*-
"""L1: metrics._safe 空值处理 + 评测 mock 函数单元测试。"""
import math

import pytest

from app.routers.metrics import _safe
from app.routers.runs import _mock_judge, _mock_llm_call


@pytest.mark.l1
class TestSafe:
    def test_nan_to_default(self):
        """ClickHouse 空表聚合的 NaN 转默认值 0。"""
        assert _safe(float("nan")) == 0
        assert _safe(math.nan) == 0

    def test_none_to_default(self):
        """None 转默认值。"""
        assert _safe(None) == 0
        assert _safe(None, default=-1) == -1

    def test_normal_value_passthrough(self):
        """正常值原样透传。"""
        assert _safe(3.14) == 3.14
        assert _safe(0) == 0


@pytest.mark.l1
class TestMockEval:
    def test_mock_llm_call_render(self):
        """mock 调用把 {{input}} 替换为真实输入。"""
        out = _mock_llm_call("请翻译:{{input}}", "你好")
        assert out == "请翻译:你好"
        assert "{{input}}" not in out

    def test_mock_judge_tie_when_same_output(self):
        """A/B 输出相同时判平局 5:5。"""
        sa, sb, reason = _mock_judge("same", "same")
        assert sa == sb == 5.0
        assert "平局" in reason

    def test_mock_judge_a_wins_when_diff(self):
        """输出不同时 A 略优 6:4。"""
        sa, sb, _ = _mock_judge("out-a", "out-b")
        assert (sa, sb) == (6.0, 4.0)
