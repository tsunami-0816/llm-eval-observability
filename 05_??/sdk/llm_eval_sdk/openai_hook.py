"""openai SDK 自动 hook：monkey patch，业务方装了 SDK 就自动上报。"""
import logging
import time
from typing import Any

from llm_eval_sdk.cost import calc_cost
from llm_eval_sdk.reporter import send_trace

logger = logging.getLogger("llm_eval_sdk")

_patched = False


def patch_openai():
    """Monkey patch Completions.create，自动上报 trace。失败降级为手动模式，不影响 init。"""
    global _patched
    if _patched:
        return

    # 修复-Q002: 原实现 patch OpenAI.chat.completions.create（实例属性当类属性）直接 AttributeError，
    # 导致 init_tracer 崩溃；改为 patch openai v1 的 Completions.create 类方法，并整体兜底。
    try:
        from openai.resources.chat.completions import Completions
    except ImportError:
        return  # 未装 openai，跳过 hook（手动装饰器模式仍可用）
    except Exception as e:
        logger.warning(f"openai hook skipped (degraded to manual mode): {e}")
        return

    original_create = Completions.create

    def patched_create(self, *args, **kwargs) -> Any:
        model = kwargs.get("model", "unknown")
        messages = kwargs.get("messages", [])
        prompt_text = "\n".join(m.get("content", "") for m in messages)[:100000]

        start = time.time()
        try:
            result = original_create(self, *args, **kwargs)
            latency_ms = int((time.time() - start) * 1000)

            output_text = result.choices[0].message.content[:100000] if result.choices else ""
            prompt_tokens = result.usage.prompt_tokens if result.usage else 0
            completion_tokens = result.usage.completion_tokens if result.usage else 0
            cost = calc_cost(model, prompt_tokens, completion_tokens)

            send_trace({
                "model": model,
                "prompt_text": prompt_text,
                "output_text": output_text,
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
                "prompt_text": prompt_text,
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

    # 修复-Q002: patch 类方法并兜底，任何 patch 失败不阻塞业务 init
    try:
        Completions.create = patched_create
        _patched = True
    except Exception as e:
        logger.warning(f"openai hook patch failed (degraded to manual mode): {e}")
