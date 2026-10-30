# -*- coding: utf-8 -*-
"""第 7.5 步：测试数据重置与干净环境交接。
用法：python scripts/reset_test_data.py
动作：MySQL 业务表清库 + 最小种子；ClickHouse trace_records TRUNCATE；Redis db3 FLUSHDB。
前置：必须先完成备份（07_联调/backup_*）。本脚本不含备份逻辑。
"""
import io
import sys
from pathlib import Path

import clickhouse_connect
import pymysql
import redis

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


def _load_env() -> dict:
    """修复-SEC002: 密码从 backend/.env 读，源码不落硬编码密钥。"""
    env = {}
    for line in (Path(__file__).resolve().parents[1] / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


_E = _load_env()
MYSQL = dict(host=_E["MYSQL_HOST"], port=int(_E["MYSQL_PORT"]), user=_E["MYSQL_USER"],
             password=_E["MYSQL_PASSWORD"], database=_E["MYSQL_DB"], charset="utf8mb4")
CH = dict(host=_E["CLICKHOUSE_HOST"], port=int(_E["CLICKHOUSE_HTTP_PORT"]),
          username=_E["CLICKHOUSE_USER"], password=_E["CLICKHOUSE_PASSWORD"])
REDIS = dict(host=_E["REDIS_HOST"], port=int(_E["REDIS_PORT"]), db=int(_E["REDIS_DB"]))


def reset_mysql():
    conn = pymysql.connect(**MYSQL)
    with conn.cursor() as cur:
        before = {}
        for t in ["prompt_version", "eval_dataset", "eval_case", "eval_run", "eval_result"]:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            before[t] = cur.fetchone()[0]

        cur.execute("SET FOREIGN_KEY_CHECKS=0")
        for t in ["eval_result", "eval_run", "eval_case", "eval_dataset", "prompt_version"]:
            cur.execute(f"TRUNCATE TABLE {t}")
        cur.execute("SET FOREIGN_KEY_CHECKS=1")

        # 最小种子：1 个 prompt 的 2 个版本（供 A/B）+ 1 个评测集（3 条中文 case）
        cur.executemany(
            "INSERT INTO prompt_version (project_id, name, version, content, description, created_at) "
            "VALUES (1, %s, %s, %s, %s, NOW())",
            [
                ("翻译助手", "v1.0", "请把以下内容翻译成英文:{{input}}", "种子-基线版"),
                ("翻译助手", "v2.0", "请将以下内容精准地翻译为英文，保持原意:{{input}}", "种子-优化版"),
            ],
        )
        cur.execute(
            "INSERT INTO eval_dataset (project_id, name, description, created_at) "
            "VALUES (1, '种子-翻译评测集', '第7.5步最小种子', NOW())"
        )
        ds_id = cur.lastrowid
        cur.executemany(
            "INSERT INTO eval_case (dataset_id, input, expected_output, scoring_criteria, created_at) "
            "VALUES (%s, %s, %s, %s, NOW())",
            [
                (ds_id, "你好，世界", "Hello, World", "准确性"),
                (ds_id, "人工智能改变世界", "AI is changing the world", "流畅性"),
                (ds_id, "今天天气怎么样", "How is the weather today", "完整性"),
            ],
        )
        after = {}
        for t in ["project", "prompt_version", "eval_dataset", "eval_case", "eval_run", "eval_result"]:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            after[t] = cur.fetchone()[0]
    conn.commit()
    conn.close()
    return before, after


def reset_clickhouse():
    c = clickhouse_connect.get_client(**CH)
    before = c.query("SELECT count() FROM trace_records").result_rows[0][0]
    c.command("TRUNCATE TABLE trace_records")
    after = c.query("SELECT count() FROM trace_records").result_rows[0][0]
    c.close()
    return before, after


def reset_redis():
    r = redis.Redis(**REDIS)
    before = r.dbsize()
    r.flushdb()
    return before, r.dbsize()


if __name__ == "__main__":
    mb, ma = reset_mysql()
    print(f"MySQL 重置前行数: {mb}")
    print(f"MySQL 重置后行数: {ma}")
    cb, ca = reset_clickhouse()
    print(f"ClickHouse trace_records: {cb} -> {ca}")
    rb, ra = reset_redis()
    print(f"Redis db3 keys: {rb} -> {ra}")
    print("✅ 重置完成")
