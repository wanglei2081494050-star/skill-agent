"""Restricted execution of a skill's attached script.

The script runs in a throwaway copy of the skill directory, with:

* a hard timeout (``SCRIPT_TIMEOUT_SECONDS``),
* network access disabled by installing a ``sitecustomize`` that makes
  ``socket.socket`` and ``urllib`` fail,
* a stripped environment (no API keys, no credentials),
* output capped at ``SCRIPT_MAX_OUTPUT_BYTES``.

This is a Python-level restriction, not an OS sandbox: it stops accidental
network calls and runaway loops from a skill script, and is documented as such.
A production deployment should run the same entry point inside a container or a
job object with a restricted token.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from .config import SCRIPT_MAX_OUTPUT_BYTES, SCRIPT_TIMEOUT_SECONDS
from .skills import Skill
from .tools import resolve_skill_file

NET_BLOCK = '''\
"""Injected guard: refuse socket creation and DNS resolution."""
import socket


class _Blocked(RuntimeError):
    pass


def _deny(*args, **kwargs):
    raise _Blocked("network access is disabled inside the skill sandbox")


socket.socket = _deny
socket.create_connection = _deny
socket.getaddrinfo = _deny
socket.gethostbyname = _deny
'''


def run_script(snapshot_skills: dict[str, Skill], name: str, rel_path: str, args: list[str]) -> dict[str, Any]:
    skill = snapshot_skills.get(name)
    if skill is None:
        return {"ok": False, "error": f"unknown skill: {name}", "exitCode": None, "stdout": "", "stderr": ""}
    try:
        script = resolve_skill_file(skill, rel_path)
    except Exception as exc:  # ToolError
        return {"ok": False, "error": str(exc), "exitCode": None, "stdout": "", "stderr": ""}
    if script.suffix.lower() not in {".py"}:
        return {
            "ok": False,
            "error": "only .py scripts can be executed by this runner",
            "exitCode": None,
            "stdout": "",
            "stderr": "",
        }

    tmp = Path(tempfile.mkdtemp(prefix="skillrun-"))
    try:
        work = tmp / skill.name
        shutil.copytree(skill.dir, work)
        (tmp / "sitecustomize.py").write_text(NET_BLOCK, encoding="utf-8")
        env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": str(tmp),
            "PYTHONDONTWRITEBYTECODE": "1",
            "SKILL_SANDBOX": "1",
            "PYTHONIOENCODING": "utf-8",
        }
        target = work / rel_path.replace("\\", "/")
        started = Path(tmp)
        try:
            proc = subprocess.run(
                # No -I here: isolated mode ignores PYTHONPATH, which would also
                # skip our injected sitecustomize and silently re-enable network.
                [sys.executable, "-c", "import sitecustomize, runpy, sys; "
                 f"sys.argv = [{str(target)!r}] + {args!r}; "
                 f"runpy.run_path({str(target)!r}, run_name='__main__')"],
                cwd=str(work),
                env=env,
                capture_output=True,
                timeout=SCRIPT_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "error": f"script timed out after {SCRIPT_TIMEOUT_SECONDS}s",
                "exitCode": None,
                "stdout": "",
                "stderr": "",
                "sandbox": {"cwd": str(work), "network": "blocked", "env": "stripped"},
            }
        stdout = proc.stdout.decode("utf-8", "replace")[:SCRIPT_MAX_OUTPUT_BYTES]
        stderr = proc.stderr.decode("utf-8", "replace")[:SCRIPT_MAX_OUTPUT_BYTES]
        return {
            "ok": proc.returncode == 0,
            "error": "" if proc.returncode == 0 else f"exit code {proc.returncode}",
            "exitCode": proc.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "sandbox": {
                "cwd": str(started),
                "network": "blocked",
                "env": "stripped",
                "timeoutSeconds": SCRIPT_TIMEOUT_SECONDS,
            },
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
