"""One real provider call, for the "call the model once and record the cost" step.

Usage:
    py -m backend.app.llm_probe "用一句话说明什么是渐进式技能披露"

Prints the reply plus the recorded input/output tokens and cost. Without a key it
prints the offline record instead of pretending a model answered.
"""

from __future__ import annotations

import sys

from . import llm


def main() -> int:
    prompt = sys.argv[1] if len(sys.argv) > 1 else "用一句话说明什么是渐进式技能披露。"
    if not llm.is_configured():
        llm.log_offline("probe", "LLM_API_KEY is not set; offline record only")
        print("LLM_API_KEY 未配置：已写入一条 offline 记录（未产生调用）。")
        print(f"日志：{llm.log_path()}")
        print("配置 key 后重跑本命令即可产生真实调用与费用记录。")
        return 2
    try:
        out = llm.chat([{"role": "user", "content": prompt}], purpose="probe", max_tokens=200)
    except llm.LLMUnavailable as exc:
        print(f"调用失败：{exc}")
        return 1
    record = out["record"]
    print(out["message"].get("content", "").strip())
    print("---")
    print(f"model={record['model']} input_tokens={record['input_tokens']} "
          f"output_tokens={record['output_tokens']} cost_usd={record['cost_usd']} "
          f"latency_ms={record['latency_ms']}")
    print(f"日志：{llm.log_path()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
