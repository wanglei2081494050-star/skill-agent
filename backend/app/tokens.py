"""Tokenizer-free token estimation.

We must not depend on ``tiktoken`` at runtime (the repo has to start with a bare
Python install), so the estimate uses the usual chat-token rule of thumb, split
for CJK: one token per CJK character/full-width punctuation, and one token per
four remaining characters. The estimate is deliberately conservative for prompt
budgeting: it over-counts slightly, which keeps us inside the real limit.
"""

from __future__ import annotations

import re

_CJK_RE = re.compile(
    "[\u3000-\u303f\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff00-\uffef]"
)


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    cjk = len(_CJK_RE.findall(text))
    other = len(text) - cjk
    return cjk + (other + 3) // 4


def cost_usd(input_tokens: int, output_tokens: int, price_in_per_m: float, price_out_per_m: float) -> float:
    return round(
        input_tokens / 1_000_000 * price_in_per_m + output_tokens / 1_000_000 * price_out_per_m,
        8,
    )
