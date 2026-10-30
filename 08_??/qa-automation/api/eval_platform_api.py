# -*- coding: utf-8 -*-
"""业务接口封装：一个模块一组方法，薄封装在 ApiClient 之上。"""


class PromptApi:
    def __init__(self, client):
        self.c = client

    def create(self, name, version, content, description="", project_id=1):
        return self.c.post("/api/prompts", json={
            "project_id": project_id, "name": name, "version": version,
            "content": content, "description": description})

    def list(self):
        return self.c.get("/api/prompts")

    def rollback(self, prompt_id):
        return self.c.post(f"/api/prompts/rollback/{prompt_id}")


class DatasetApi:
    def __init__(self, client):
        self.c = client

    def create(self, name, description="", project_id=1):
        return self.c.post("/api/datasets", json={
            "project_id": project_id, "name": name, "description": description})

    def list(self):
        return self.c.get("/api/datasets")

    def import_cases(self, dataset_id, cases):
        return self.c.post(f"/api/datasets/{dataset_id}/cases", json={"cases": cases})

    def list_cases(self, dataset_id):
        return self.c.get(f"/api/datasets/{dataset_id}/cases")


class RunApi:
    def __init__(self, client):
        self.c = client

    def create(self, dataset_id, prompt_a_id, prompt_b_id):
        return self.c.post("/api/runs", json={
            "dataset_id": dataset_id, "prompt_a_id": prompt_a_id,
            "prompt_b_id": prompt_b_id})

    def list(self):
        return self.c.get("/api/runs")

    def detail(self, run_id):
        return self.c.get(f"/api/runs/{run_id}")


class TraceApi:
    def __init__(self, client):
        self.c = client

    def report(self, records: list[dict]):
        return self.c.post("/api/traces", json=records)

    def get(self, trace_id):
        return self.c.get(f"/api/traces/{trace_id}")


class MetricApi:
    def __init__(self, client):
        self.c = client

    def summary(self, range_days=7):
        return self.c.get("/api/metrics/summary", params={"range_days": range_days})

    def timeseries(self, metric="latency", range_days=7):
        return self.c.get("/api/metrics/timeseries",
                          params={"metric": metric, "range_days": range_days})


def make_trace(trace_id=None, model="qa-model", source="openai", status="success",
               prompt="qa-prompt", output="qa-output", latency_ms=100, **over):
    """造一条合法 trace 记录。"""
    import uuid
    rec = {
        "trace_id": trace_id or str(uuid.uuid4()),
        "project_id": 1, "model": model,
        "prompt_text": prompt, "output_text": output,
        "prompt_tokens": max(len(prompt) // 4, 1),
        "completion_tokens": max(len(output) // 4, 1),
        "cost_usd": 0.0001, "latency_ms": latency_ms,
        "source": source, "status": status, "error_message": "",
    }
    rec.update(over)
    return rec
