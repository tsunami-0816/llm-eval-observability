"""成本核算表：按 model + tokens 算 USD 成本（M6：误差 ≤1%）。"""

# 单位：USD / 1K tokens
COST_TABLE: dict[str, dict[str, float]] = {
    # OpenAI
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    # DeepSeek
    "deepseek-chat": {"input": 0.00014, "output": 0.00028},
    "deepseek-reasoner": {"input": 0.00055, "output": 0.00219},
    # 通用 fallback（未知 model 按 gpt-4o-mini 算）
    "_default": {"input": 0.00015, "output": 0.0006},
}


def calc_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """根据 model 和 tokens 算成本（USD）。"""
    price = COST_TABLE.get(model, COST_TABLE["_default"])
    cost = (prompt_tokens / 1000) * price["input"] + (completion_tokens / 1000) * price["output"]
    return round(cost, 6)
