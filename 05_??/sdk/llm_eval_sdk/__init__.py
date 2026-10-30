"""llm-eval-sdk: 一行接入，自动上报 LLM 调用 trace。"""
from llm_eval_sdk.tracer import init_tracer, trace_call

__all__ = ["init_tracer", "trace_call"]
