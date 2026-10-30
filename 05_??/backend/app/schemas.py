"""Pydantic 请求/响应模型。"""
from pydantic import BaseModel, Field


class TraceRecordIn(BaseModel):
    trace_id: str
    project_id: int = 1
    model: str
    prompt_text: str = Field(max_length=100000)
    output_text: str = Field(max_length=100000)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    source: str = "openai"
    status: str = "success"
    error_message: str = ""


class PromptCreate(BaseModel):
    project_id: int = 1
    name: str = Field(max_length=64)
    version: str = Field(max_length=32)
    content: str = Field(max_length=100000)
    description: str = ""


class DatasetCreate(BaseModel):
    project_id: int = 1
    name: str = Field(max_length=64)
    description: str = ""


class CaseBatchIn(BaseModel):
    cases: list[dict]  # [{input, expected_output, scoring_criteria}]


class RunCreate(BaseModel):
    dataset_id: int
    prompt_a_id: int
    prompt_b_id: int
