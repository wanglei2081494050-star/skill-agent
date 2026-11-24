"""HTTP API for the demo page (stdlib only, no framework dependency)."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from . import agent, eval as eval_mod, llm
from .bulk import BULK
from .config import PROMPT_BUDGET_TOKENS
from .inject import build_skill_section
from .sandbox import run_script
from .skills import SkillRegistry
from .tools import ToolError, load_skill, read_skill_file

REGISTRY = SkillRegistry()
TURNS: list[dict[str, Any]] = []
MAX_TURNS_KEPT = 50


def _extra_skills(simulate: bool) -> list:
    return BULK.skills(200) if simulate else []


def _state(budget: int, simulate: bool) -> dict[str, Any]:
    snapshot = REGISTRY.snapshot()
    build = build_skill_section(snapshot, budget=budget, extra_skills=_extra_skills(simulate))
    base = build_skill_section(snapshot, budget=budget)
    return {
        "skills": snapshot.summary(),
        "prompt": {
            "current": build.summary(),
            "withoutSimulation": {
                "tokens": base.tokens,
                "level": base.level,
                "count": len(base.included),
            },
            "simulation": {
                "enabled": simulate,
                "skills": len(BULK.skills(200)) if simulate else 0,
            },
        },
        "llm": {
            "configured": llm.is_configured(),
            "model": llm.basic_model_info(),
            "totals": llm.totals(),
            "calls": llm.read_calls(limit=15),
        },
        "turns": TURNS[-20:],
    }


def _json(handler: BaseHTTPRequestHandler, payload: Any, status: int = 200) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
    handler.end_headers()
    handler.wfile.write(body)


class Handler(BaseHTTPRequestHandler):
    server_version = "skill-agent/0.1"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:  # quieter dev log
        sys.stderr.write("[api] " + fmt % args + "\n")

    # -- helpers --------------------------------------------------------
    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

    def do_OPTIONS(self) -> None:  # noqa: N802
        _json(self, {"ok": True})

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        def qbool(key: str) -> bool:
            return (query.get(key, ["0"])[0] or "").lower() in {"1", "true", "yes", "on"}

        def qint(key: str, default: int) -> int:
            try:
                return int(query.get(key, [str(default)])[0])
            except ValueError:
                return default

        if parsed.path == "/health":
            _json(
                self,
                {
                    "status": "ok",
                    "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "scans": REGISTRY.rescan_count,
                },
            )
            return
        if parsed.path == "/api/state":
            _json(self, _state(qint("budget", PROMPT_BUDGET_TOKENS), qbool("simulate")))
            return
        if parsed.path == "/api/prompt":
            snapshot = REGISTRY.snapshot()
            build = build_skill_section(
                snapshot, budget=qint("budget", PROMPT_BUDGET_TOKENS), extra_skills=_extra_skills(qbool("simulate"))
            )
            _json(self, build.summary())
            return
        if parsed.path == "/api/eval":
            report_path = eval_mod.EVAL_REPORT_DIR / "latest.json"
            if report_path.exists():
                _json(self, json.loads(report_path.read_text(encoding="utf-8")))
            else:
                _json(self, {"variants": {}, "note": "no eval run yet"})
            return
        if parsed.path == "/api/llm/logs":
            _json(self, {"totals": llm.totals(), "calls": llm.read_calls(limit=qint("limit", 50))})
            return
        _json(self, {"error": "not found", "path": parsed.path}, status=404)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        body = self._body()

        if parsed.path == "/api/scan":
            snapshot = REGISTRY.rescan()
            _json(self, {"ok": True, "fingerprint": snapshot.fingerprint, "skills": len(snapshot.skills)})
            return

        if parsed.path == "/api/chat":
            message = str(body.get("message") or "").strip()
            if not message:
                _json(self, {"error": "message must not be empty"}, status=400)
                return
            budget = int(body.get("budget") or PROMPT_BUDGET_TOKENS)
            simulate = bool(body.get("simulate"))
            snapshot = REGISTRY.snapshot()
            turn = agent.run_turn(
                snapshot, message, budget=budget, extra_skills=_extra_skills(simulate)
            )
            TURNS.append(turn)
            del TURNS[:-MAX_TURNS_KEPT]
            _json(self, turn)
            return

        if parsed.path == "/api/load":
            snapshot = REGISTRY.snapshot()
            try:
                result = load_skill(snapshot, str(body.get("name") or ""))
            except ToolError as exc:
                _json(self, {"error": str(exc)}, status=400)
                return
            _json(self, result)
            return

        if parsed.path == "/api/file":
            snapshot = REGISTRY.snapshot()
            try:
                result = read_skill_file(
                    snapshot, str(body.get("name") or ""), str(body.get("path") or "")
                )
            except ToolError as exc:
                _json(self, {"error": str(exc)}, status=400)
                return
            _json(self, result)
            return

        if parsed.path == "/api/script":
            snapshot = REGISTRY.snapshot()
            result = run_script(
                snapshot.by_name(),
                str(body.get("name") or ""),
                str(body.get("path") or ""),
                [str(a) for a in (body.get("args") or [])],
            )
            _json(self, result)
            return

        if parsed.path == "/api/eval/run":
            snapshot = REGISTRY.snapshot()
            report = eval_mod.run_all(snapshot)
            path = eval_mod.persist(report)
            _json(self, {"ok": True, "report": report, "path": str(path)})
            return

        _json(self, {"error": "not found", "path": parsed.path}, status=404)


def main() -> None:
    port = int(os.environ.get("PORT") or (sys.argv[1] if len(sys.argv) > 1 else 8787))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    snapshot = REGISTRY.snapshot()
    print(
        f"[api] listening on http://127.0.0.1:{port}  skills={len(snapshot.skills)} "
        f"skipped={len(snapshot.skipped)} conflicts={len(snapshot.conflicts)}",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
