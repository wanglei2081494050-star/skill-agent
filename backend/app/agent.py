"""One chat turn: route -> inject -> load body -> read attached files -> answer.

Two execution modes share one trace shape:

``online``   the configured OpenAI-compatible model decides which skill to load
             through real tool calls;
``offline``  the deterministic BM25 router decides, then the same tools are
             executed in code. This keeps the demo and the eval harness usable
             without an API key, and every trace labels the mode explicitly.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from . import llm
from .config import MAX_TOOL_ROUNDS
from .inject import build_skill_section
from .router import route
from .skills import Skill, Snapshot
from .tools import ToolError, load_skill, read_skill_file

ATTACHED_REF = re.compile(
    r"(?<![\w/])((?:templates|scripts|references|assets)/[A-Za-z0-9_.\-/]+\.[A-Za-z0-9]{1,6})"
)

TOOL_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "load_skill",
            "description": (
                "Load the full body of one skill by name. Also returns the bodies of "
                "its declared dependencies. Call this before doing the task."
            ),
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string", "description": "skill name"}},
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_skill_file",
            "description": (
                "Read one attached file of a skill. Path must be relative to the skill "
                "directory (e.g. templates/outline.md)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "path": {"type": "string"},
                },
                "required": ["name", "path"],
            },
        },
    },
]

SYSTEM_PREFIX = (
    "You are a task agent with progressive-disclosure skills. "
    "Answer in the user's language. Keep answers short and operational. "
    "When a skill matches the request, call load_skill first, then read the attached "
    "files the body references before answering.\n\n"
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _referenced_files(body: str, attached: list[str]) -> list[str]:
    found: list[str] = []
    for match in ATTACHED_REF.findall(body):
        if match in attached and match not in found:
            found.append(match)
    return found[:3]


def _compose_offline_reply(
    skill: Skill, body: str, files: list[dict[str, Any]], texts: dict[str, str] | None = None
) -> str:
    steps = []
    for line in body.splitlines():
        stripped = line.strip()
        if re.match(r"^\d+\.\s+", stripped):
            steps.append(re.sub(r"^\d+\.\s+", "", stripped))
    head = f"已加载技能 `{skill.name}`（来源 {skill.source_id}，正文 {skill.body_tokens} tokens）。"
    if files:
        head += " 读取附带文件：" + "、".join(f"`{f['path']}`" for f in files) + "。"
    lines = [head, "", "按技能正文的步骤执行："]
    lines += [f"{i}. {step}" for i, step in enumerate(steps[:6], start=1)]
    if not steps:
        lines.append("1. 正文没有编号步骤，按正文说明执行。")
    texts = texts or {}
    previews = [(f["path"], texts[f["path"]]) for f in files if f["path"] in texts]
    if previews:
        first_path, first_text = previews[0]
        preview = "\n".join(first_text.splitlines()[:6])
        lines += ["", f"`{first_path}` 前几行：", "```", preview, "```"]
    lines += ["", "（offline 模式：以上由确定性路由器选择技能并直接执行工具，未调用大模型。）"]
    return "\n".join(lines)


def run_turn(
    snapshot: Snapshot,
    message: str,
    budget: int | None = None,
    extra_skills: list[Skill] | None = None,
) -> dict[str, Any]:
    turn_id = uuid.uuid4().hex[:12]
    steps: list[dict[str, Any]] = []
    loaded: list[str] = []
    files_read: list[dict[str, Any]] = []

    prompt = build_skill_section(snapshot, budget=budget or 800, extra_skills=extra_skills)
    steps.append(
        {
            "type": "inject",
            "detail": f"skill section {prompt.tokens}/{prompt.budget} tokens, level={prompt.level}, "
            f"{len(prompt.included)} skills listed",
            "tokens": prompt.tokens,
            "budget": prompt.budget,
            "level": prompt.level,
        }
    )
    system_prompt = SYSTEM_PREFIX + prompt.text

    decision = route(message, snapshot.skills)
    steps.append(
        {
            "type": "route",
            "detail": f"pre-router suggests {decision['skill'] or 'no skill'} (score {decision['score']})",
            "top": decision["top"],
        }
    )

    mode = "online" if llm.is_configured() else "offline"
    reply = ""
    usage = {"inputTokens": 0, "outputTokens": 0, "costUsd": 0.0, "calls": 0}

    if mode == "offline":
        target = decision["skill"]
        if target is None:
            reply = (
                "offline 模式的确定性路由器判断这条请求不需要任何技能（最高匹配分 "
                f"{decision['score']} 低于阈值 {decision['threshold']}），因此直接用通用回答处理。"
            )
        else:
            try:
                result = load_skill(snapshot, target)
            except ToolError as exc:
                steps.append({"type": "tool_error", "detail": str(exc)})
                reply = f"加载技能失败：{exc}"
            else:
                loaded.extend(result["order"])
                steps.append(
                    {
                        "type": "tool_call",
                        "name": "load_skill",
                        "args": {"name": target},
                        "detail": f"loaded {', '.join(result['order'])}",
                    }
                )
                skill = snapshot.get(target)
                assert skill is not None
                file_texts: dict[str, str] = {}
                for rel in _referenced_files(result["body"], skill.attached):
                    try:
                        data = read_skill_file(snapshot, target, rel)
                    except ToolError as exc:
                        steps.append({"type": "tool_error", "detail": str(exc)})
                        continue
                    files_read.append({"skill": target, "path": rel, "bytes": data["bytes"]})
                    file_texts[rel] = data["text"]
                    steps.append(
                        {
                            "type": "tool_call",
                            "name": "read_skill_file",
                            "args": {"name": target, "path": rel},
                            "detail": f"read {rel} ({data['bytes']} bytes)",
                        }
                    )
                reply = _compose_offline_reply(skill, result["body"], files_read, file_texts)
    else:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ]
        try:
            for _ in range(MAX_TOOL_ROUNDS):
                out = llm.chat(messages, purpose="chat", tools=TOOL_SCHEMA)
                usage["calls"] += 1
                usage["inputTokens"] += out["record"]["input_tokens"]
                usage["outputTokens"] += out["record"]["output_tokens"]
                usage["costUsd"] = round(usage["costUsd"] + out["record"]["cost_usd"], 8)
                msg = out["message"]
                tool_calls = msg.get("tool_calls") or []
                if tool_calls:
                    messages.append(
                        {
                            "role": "assistant",
                            "content": msg.get("content") or "",
                            "tool_calls": tool_calls,
                        }
                    )
                    for call in tool_calls:
                        fn = call.get("function", {})
                        name = fn.get("name", "")
                        try:
                            args = json.loads(fn.get("arguments") or "{}")
                        except json.JSONDecodeError:
                            args = {}
                        steps.append(
                            {
                                "type": "tool_call",
                                "name": name,
                                "args": args,
                                "detail": f"model requested {name}",
                            }
                        )
                        try:
                            if name == "load_skill":
                                result = load_skill(snapshot, str(args.get("name", "")))
                                loaded.extend(result["order"])
                                payload = {
                                    "order": result["order"],
                                    "body": result["body"],
                                    "attached": result["attached"],
                                    "dependencies": result["dependencies"],
                                    "missingDependencies": result["missingDependencies"],
                                }
                            elif name == "read_skill_file":
                                data = read_skill_file(
                                    snapshot, str(args.get("name", "")), str(args.get("path", ""))
                                )
                                files_read.append(
                                    {
                                        "skill": data["skill"],
                                        "path": data["path"],
                                        "bytes": data["bytes"],
                                    }
                                )
                                payload = {"path": data["path"], "text": data["text"]}
                            else:
                                raise ToolError(f"unknown tool: {name}")
                            content = json.dumps(payload, ensure_ascii=False)
                        except ToolError as exc:
                            steps.append({"type": "tool_error", "detail": str(exc)})
                            content = json.dumps({"error": str(exc)}, ensure_ascii=False)
                        messages.append(
                            {"role": "tool", "tool_call_id": call.get("id", ""), "content": content}
                        )
                    continue
                reply = (msg.get("content") or "").strip() or "(model returned an empty message)"
                break
            else:
                reply = "已达到工具调用轮次上限，未得到最终回答。"
        except llm.LLMUnavailable as exc:
            steps.append({"type": "tool_error", "detail": f"model unavailable: {exc}"})
            reply = f"模型调用失败：{exc}"

    return {
        "id": turn_id,
        "ts": _now(),
        "message": message,
        "mode": mode,
        "reply": reply,
        "steps": steps,
        "loaded": loaded,
        "files": files_read,
        "prompt": {
            "tokens": prompt.tokens,
            "budget": prompt.budget,
            "level": prompt.level,
            "included": prompt.included,
            "omitted": prompt.omitted,
        },
        "usage": usage,
        "fingerprint": snapshot.fingerprint,
        "systemPrompt": system_prompt,
    }
