# -*- coding: utf-8 -*-
"""requests 封装：自动带 x-api-key、打请求/响应日志。"""
import logging
import os
import re

import requests
import yaml

logger = logging.getLogger("qa")


def load_config() -> dict:
    path = os.path.join(os.path.dirname(__file__), "..", "config", "config.yaml")
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    # 展开 ${VAR:default} 占位
    raw = re.sub(r"\$\{(\w+):([^}]*)\}", lambda m: os.environ.get(m.group(1), m.group(2)), raw)
    return yaml.safe_load(raw)


class ApiClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers["X-API-Key"] = api_key

    def request(self, method: str, path: str, **kwargs) -> requests.Response:
        url = self.base_url + path
        logger.info("%s %s kwargs=%s", method, url, {k: v for k, v in kwargs.items() if k != "json"})
        resp = self.session.request(method, url, timeout=30, **kwargs)
        logger.info("-> %s %s", resp.status_code, resp.text[:300])
        return resp

    def get(self, path, **kw):
        return self.request("GET", path, **kw)

    def post(self, path, **kw):
        return self.request("POST", path, **kw)
