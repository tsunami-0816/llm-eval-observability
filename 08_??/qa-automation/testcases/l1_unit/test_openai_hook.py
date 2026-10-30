# -*- coding: utf-8 -*-
"""L1: openai hook 单元测试（不发起真实 LLM 请求）。"""
import pytest

import llm_eval_sdk.openai_hook as hook_mod
from llm_eval_sdk.openai_hook import patch_openai


@pytest.mark.l1
class TestOpenAiHook:
    def test_patch_marks_patched(self):
        """patch 后模块标记 _patched=True，Completions.create 被换成包装函数。"""
        from openai.resources.chat.completions import Completions
        patch_openai()
        assert hook_mod._patched is True
        assert Completions.create.__name__ == "patched_create"

    def test_patch_idempotent(self):
        """重复 patch 不叠加包装（幂等）。"""
        from openai.resources.chat.completions import Completions
        patch_openai()
        first = Completions.create
        patch_openai()
        assert Completions.create is first, "重复 patch 不应再次包装"

    def test_error_path_reports_and_reraises(self, monkeypatch):
        """原 create 异常时：上报 status=error 记录，异常原样抛给业务方。"""
        from openai.resources.chat.completions import Completions
        patch_openai()
        sent = []
        monkeypatch.setattr(hook_mod, "send_trace", lambda rec: sent.append(rec))
        # self=None 使内部 original_create 必抛 AttributeError
        with pytest.raises(Exception):
            Completions.create(None, model="gpt-4o",
                               messages=[{"role": "user", "content": "hi"}])
        assert sent, "异常路径也应上报一条 error trace"
        assert sent[-1]["status"] == "error"
        assert sent[-1]["model"] == "gpt-4o"
