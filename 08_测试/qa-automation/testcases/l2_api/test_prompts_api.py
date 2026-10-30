# -*- coding: utf-8 -*-
"""L2: Prompt 接口四象限测试（正向/反向/边界/越权）。"""
import pytest

from common.assert_util import assert_fail, assert_ok


@pytest.mark.l2
class TestPromptsApi:
    @pytest.mark.p0
    def test_create_prompt_success(self, make_prompt, prompt_api):
        """正向：创建 prompt 后列表可查，字段原样。"""
        created = make_prompt(name="qa-正向", version="v9.9", content="内容{{input}}")
        prompts = assert_ok(prompt_api.list())
        hit = [p for p in prompts if p["id"] == created["id"]]
        assert hit, "新建 prompt 应出现在列表"
        assert hit[0]["name"] == "qa-正向"
        assert hit[0]["version"] == "v9.9"
        assert hit[0]["content"] == "内容{{input}}"

    def test_create_prompt_missing_field_422(self, prompt_api):
        """反向：缺必填字段 content 返回 422。"""
        resp = prompt_api.c.post("/api/prompts", json={"name": "x", "version": "v1"})
        assert_fail(resp, 422)

    def test_create_prompt_name_too_long_422(self, prompt_api):
        """边界：name 超 64 字符返回 422。"""
        resp = prompt_api.c.post("/api/prompts", json={
            "name": "n" * 65, "version": "v1", "content": "c"})
        assert_fail(resp, 422)

    def test_create_prompt_chinese_roundtrip(self, make_prompt, mysql_conn):
        """正向+utf8mb4：中文内容入库后 API 回读与 DB 直查均不裂化。"""
        created = make_prompt(name="qa-中文", version="v1", content="请把以下内容翻译成英文:{{input}}")
        with mysql_conn.cursor() as cur:
            cur.execute("SELECT name, content FROM prompt_version WHERE id=%s", (created["id"],))
            name, content = cur.fetchone()
        assert name == "qa-中文"
        assert content == "请把以下内容翻译成英文:{{input}}"

    def test_rollback_success(self, make_prompt, prompt_api, mysql_conn):
        """正向：rollback 生成 {version}-rollback 新版本，内容继承。"""
        created = make_prompt(name="qa-回滚", version="v1.0", content="原版内容{{input}}")
        data = assert_ok(prompt_api.rollback(created["id"]))
        new_id = data["id"]
        # 清理新版本
        with mysql_conn.cursor() as cur:
            cur.execute("SELECT version, content FROM prompt_version WHERE id=%s", (new_id,))
            row = cur.fetchone()
            cur.execute("DELETE FROM prompt_version WHERE id=%s", (new_id,))
        assert row[0] == "v1.0-rollback"
        assert row[1] == "原版内容{{input}}"

    def test_rollback_not_found_404(self, prompt_api):
        """反向：rollback 不存在的 id 返回 404。"""
        assert_fail(prompt_api.rollback(99999999), 404)
