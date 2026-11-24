"""LLM wrapper: one place that talks to the provider and logs cost.

Every call (successful or not) appends one JSON line to
``data/llm_calls.jsonl`` with the model, the input/output token counts reported
by the provider, and the computed cost in USD. When no API key is configured the
wrapper raises ``LLMUnavailable`` and callers fall back to the deterministic
offline router, which is marked ``mode="offline"`` in every trace so the demo
never pretends a model answered.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import (
    DATA_DIR,
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
    LLM_TIMEOUT_SECONDS,
    PRICE_INPUT_PER_M,
    PRICE_OUTPUT_PER_M,
)
from .tokens import cost_usd, estimate_tokens

LOG_PATH = DATA_DIR / "llm_calls.jsonl"


class LLMUnavailable(RuntimeError):
    """No key configured, or the provider refused the request."""


@dataclass
class CallRecord:
    ts: str
    model: str
    mode: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int
    purpose: str
    ok: bool = True
    error: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ts": self.ts,
            "model": self.model,
            "mode": self.mode,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": self.cost_usd,
            "latency_ms": self.latency_ms,
            "purpose": self.purpose,
            "ok": self.ok,
            "error": self.error,
            "meta": self.meta,
        }


def _append(record: CallRecord) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record.as_dict(), ensure_ascii=False) + "\n")


def log_offline(purpose: str, reason: str, input_tokens: int = 0, output_tokens: int = 0) -> CallRecord:
    record = CallRecord(
        ts=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        model="offline-heuristic",
        mode="offline",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=0.0,
        latency_ms=0,
        purpose=purpose,
        ok=False,
        error=reason,
    )
    _append(record)
    return record


def is_configured() -> bool:
    return bool(LLM_API_KEY)


def chat(
    messages: list[dict[str, Any]],
    purpose: str,
    tools: list[dict[str, Any]] | None = None,
    temperature: float = 0.0,
    max_tokens: int = 900,
) -> dict[str, Any]:
    """One chat-completions call. Returns ``{"message", "record"}``."""
    if not is_configured():
        raise LLMUnavailable("LLM_API_KEY is not set")

    payload: dict[str, Any] = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    url = LLM_BASE_URL.rstrip("/") + "/chat/completions"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {LLM_API_KEY}",
        },
        method="POST",
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=LLM_TIMEOUT_SECONDS) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        detail = getattr(exc, "read", lambda: b"")()
        text = detail.decode("utf-8", "replace")[:400] if detail else str(exc)
        record = CallRecord(
            ts=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            model=LLM_MODEL,
            mode="online",
            input_tokens=0,
            output_tokens=0,
            cost_usd=0.0,
            latency_ms=int((time.monotonic() - started) * 1000),
            purpose=purpose,
            ok=False,
            error=text,
        )
        _append(record)
        raise LLMUnavailable(f"provider call failed: {text}") from exc

    usage = body.get("usage") or {}
    input_tokens = int(usage.get("prompt_tokens") or 0)
    output_tokens = int(usage.get("completion_tokens") or 0)
    if not input_tokens:
        input_tokens = estimate_tokens(json.dumps(messages, ensure_ascii=False))
    record = CallRecord(
        ts=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        model=body.get("model", LLM_MODEL),
        mode="online",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd(input_tokens, output_tokens, PRICE_INPUT_PER_M, PRICE_OUTPUT_PER_M),
        latency_ms=int((time.monotonic() - started) * 1000),
        purpose=purpose,
        meta={"requested_model": LLM_MODEL},
    )
    _append(record)
    choice = (body.get("choices") or [{}])[0]
    return {"message": choice.get("message") or {}, "record": record.as_dict()}


def read_calls(limit: int = 50) -> list[dict[str, Any]]:
    if not LOG_PATH.exists():
        return []
    rows: list[dict[str, Any]] = []
    with LOG_PATH.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows[-limit:][::-1]


def totals(rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    data = rows if rows is not None else read_calls(limit=10_000)
    return {
        "calls": len(data),
        "onlineCalls": sum(1 for r in data if r.get("mode") == "online"),
        "inputTokens": sum(int(r.get("input_tokens") or 0) for r in data),
        "outputTokens": sum(int(r.get("output_tokens") or 0) for r in data),
        "costUsd": round(sum(float(r.get("cost_usd") or 0) for r in data), 8),
    }


def basic_model_info() -> dict[str, Any]:
    return {
        "model": LLM_MODEL,
        "baseUrl": LLM_BASE_URL,
        "configured": is_configured(),
        "priceInPerMTokens": PRICE_INPUT_PER_M,
        "priceOutPerMTokens": PRICE_OUTPUT_PER_M,
    }


def log_path() -> Path:
    return LOG_PATH
