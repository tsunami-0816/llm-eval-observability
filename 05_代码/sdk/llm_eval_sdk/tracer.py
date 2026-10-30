"""trace 装饰器：包装 LLM 调用，自动记录输入/输出/延迟/token。"""
import time
from functools import wraps
from typing import Any, Callable

from llm_eval_sdk.cost import calc_cost
from llm_eval_sdk.reporter import init_reporter, send_trace
from llm_eval_sdk.openai_hook import patch_openai


def init_tracer(api_endpoint: str, api_key: str, project_id: int = 1):
    """初始化 SDK。业务方在程序入口调一次。自动 hook openai 客户端。"""
    init_reporter(api_endpoint, api_key, project_id)
    patch_openai()


def trace_call(model: str = "unknown"):
    """装饰器：包装一个 LLM 调用函数（手动模式，openai hook 已自动的话不需要）。"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            start = time.time()
            prompt_text = str(kwargs.get("prompt", args[0] if args else ""))
            try:
                result = await func(*args, **kwargs)
                latency_ms = int((time.time() - start) * 1000)
                prompt_tokens = len(prompt_text) // 4
                completion_tokens = len(str(result)) // 4
                cost = calc_cost(model, prompt_tokens, completion_tokens)
                send_trace({
                    "model": model,
                    "prompt_text": prompt_text[:100000],
                    "output_text": str(result)[:100000],
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "cost_usd": cost,
                    "latency_ms": latency_ms,
                    "source": "openai",
                    "status": "success",
                })
                return result
            except Exception as e:
                latency_ms = int((time.time() - start) * 1000)
                send_trace({
                    "model": model,
                    "prompt_text": prompt_text[:100000],
                    "output_text": "",
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "cost_usd": 0,
                    "latency_ms": latency_ms,
                    "source": "openai",
                    "status": "error",
                    "error_message": str(e)[:500],
                })
                raise

        return async_wrapper

    return decorator
