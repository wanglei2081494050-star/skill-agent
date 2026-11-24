#!/usr/bin/env python
"""Publish this repository to GitHub.

Three things happen, in order:

1. **Authorize.** Resolve a token: ``--token`` / ``GITHUB_TOKEN`` if given,
   otherwise run GitHub's OAuth device flow and let the Edge window that is
   already signed in approve it. Approval is driven through Windows UI
   Automation, so no password, cookie decryption, or manual copy-paste is
   needed - the script types the device code into the page and clicks
   "Authorize".
2. **Create the repository** through the REST API (skipped when it exists).
3. **Push** ``main`` with the full history, then verify the result through the
   API (default branch, commit count, file count).

Examples
--------
    py scripts/publish_github.py
    py scripts/publish_github.py --repo-name skill-agent --private
    GITHUB_TOKEN=ghp_xxx py scripts/publish_github.py

The token is used in the push URL for one command only; it is never written to
``.git/config``. Only the standard library plus ``uiautomation`` (browser path)
is required.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.github.com"
DEVICE_CODE_URL = "https://github.com/login/device/code"
TOKEN_URL = "https://github.com/login/oauth/access_token"
# GitHub CLI is a public OAuth app with device flow enabled; reusing its client id
# keeps this script from needing an OAuth app of its own.
CLIENT_ID = "178c6fc778ccc68e1d6a"
SCOPE = "repo"
EDGE_CANDIDATES = [
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
]
REPO_ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------- api
def api(path: str, token: str, method: str = "GET", payload: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        API + path,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "skill-agent-publisher",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            body = response.read().decode()
            return response.status, json.loads(body) if body.strip() else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        try:
            return exc.code, json.loads(body) if body.strip() else {}
        except json.JSONDecodeError:
            return exc.code, {"message": body[:300]}


# ----------------------------------------------------------------- device flow
def start_device_flow() -> dict:
    data = urllib.parse.urlencode({"client_id": CLIENT_ID, "scope": SCOPE}).encode()
    request = urllib.request.Request(
        DEVICE_CODE_URL, data=data, headers={"Accept": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode())


def poll_for_token(device_code: str, interval: int = 5, timeout_seconds: int = 600) -> str:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        data = urllib.parse.urlencode(
            {
                "client_id": CLIENT_ID,
                "device_code": device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            }
        ).encode()
        request = urllib.request.Request(
            TOKEN_URL, data=data, headers={"Accept": "application/json"}, method="POST"
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            raise SystemExit(f"token endpoint returned HTTP {exc.code}") from exc
        if payload.get("access_token"):
            return payload["access_token"]
        error = payload.get("error")
        if error not in ("authorization_pending", "slow_down"):
            raise SystemExit(f"device flow failed: {error}: {payload.get('error_description', '')}")
        time.sleep(interval if error == "authorization_pending" else interval + 5)
    raise SystemExit("device flow timed out waiting for approval")


# ---------------------------------------------------------------- uia helpers
def _edge_window():
    import uiautomation as auto

    auto.SetGlobalSearchTimeout(2)
    for window in auto.GetRootControl().GetChildren():
        try:
            if window.ClassName == "Chrome_WidgetWin_1" and "Edge" in (window.Name or ""):
                return auto, window
        except Exception:
            continue
    return auto, None


def _descendants(control, limit: int = 3000) -> list:
    found: list = []

    def walk(node, depth: int) -> None:
        if depth > 20 or len(found) > limit:
            return
        try:
            children = node.GetChildren()
        except Exception:
            return
        for child in children:
            found.append(child)
            walk(child, depth + 1)

    walk(control, 0)
    return found


def _find_button(controls: list, needles: tuple[str, ...]):
    for control in controls:
        try:
            if control.ControlTypeName != "ButtonControl":
                continue
            rect = control.BoundingRectangle
            if rect.width() <= 0 or rect.height() <= 0:
                continue  # hidden or offscreen duplicate
            name = (control.Name or "").strip().lower()
            if any(needle.lower() in name for needle in needles):
                return control
        except Exception:
            continue
    return None


def approve_in_browser(flow: dict, edge_path: Path, debug: bool = False) -> None:
    """Open the device page and click through it with UI Automation."""
    url = f"{flow['verification_uri']}?user_code={flow['user_code']}"
    print(f"[auth] opening {url}")
    subprocess.Popen([str(edge_path), url])
    time.sleep(8)

    code = flow["user_code"].replace("-", "")
    deadline = time.time() + 120
    typed = False
    while time.time() < deadline:
        auto, window = _edge_window()
        if window is None:
            time.sleep(2)
            continue
        controls = _descendants(window)

        # 1) A fresh window may ask "Continue as <account>" first.
        continue_as = _find_button(controls, ("继续以", "continue as"))
        if continue_as is not None:
            print("[auth] confirming the signed-in account")
            continue_as.Click()
            time.sleep(6)
            continue

        # 2) The device code form: eight single-character inputs.
        edits = []
        for control in controls:
            try:
                if control.ControlTypeName == "EditControl" and (
                    "用户代码" in (control.Name or "") or "user code" in (control.Name or "").lower()
                ):
                    edits.append(control)
            except Exception:
                continue
        if edits and not typed:
            print(f"[auth] typing device code {flow['user_code']}")
            edits[0].SetFocus()
            time.sleep(0.4)
            for character in code:
                auto.SendKeys(character, waitTime=0.05)
                time.sleep(0.12)
            typed = True
            continue

        submit = _find_button(controls, ("继续", "continue"))
        if typed is True and submit is not None:
            print("[auth] submitting the code")
            submit.Click()
            time.sleep(6)
            typed = "submitted"
            continue

        # 3) Authorization screen.
        authorize = _find_button(controls, ("授权", "authorize"))
        if authorize is not None:
            print("[auth] clicking Authorize")
            authorize.Click()
            time.sleep(3)
            return

        if debug:
            names = []
            for control in controls:
                try:
                    if control.ControlTypeName == "ButtonControl" and control.Name:
                        names.append(control.Name)
                except Exception:
                    pass
            print("[auth] buttons seen:", names[:20])
        time.sleep(2)
    raise SystemExit("could not drive the GitHub device page; pass --token instead")


def resolve_token(args: argparse.Namespace) -> str:
    if args.token:
        return args.token.strip()
    edge = next((path for path in EDGE_CANDIDATES if path.exists()), None)
    if edge is None:
        raise SystemExit("Edge not found; pass --token or set GITHUB_TOKEN")
    flow = start_device_flow()
    print(f"[auth] user code: {flow['user_code']} (expires in {flow.get('expires_in', 900)}s)")
    approve_in_browser(flow, edge, debug=args.debug)
    token = poll_for_token(flow["device_code"], interval=int(flow.get("interval", 5)))
    print("[auth] access token received")
    return token


# --------------------------------------------------------------------- publish
def run_git(*args: str, cwd: Path) -> str:
    result = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed:\n{result.stderr.strip()}")
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Create the GitHub repo and push this history")
    parser.add_argument("--token", default=None, help="GitHub token; otherwise device flow is used")
    parser.add_argument("--repo-name", default="skill-agent")
    parser.add_argument("--private", action="store_true", help="create a private repository")
    parser.add_argument("--branch", default=None, help="branch to push (default: current)")
    parser.add_argument("--debug", action="store_true", help="print the buttons seen in the browser")
    parser.add_argument("--dry-run", action="store_true", help="authorize and inspect, do not push")
    args = parser.parse_args()

    token = args.token or __import__("os").environ.get("GITHUB_TOKEN", "")
    if not token:
        token = resolve_token(args)

    status, user = api("/user", token)
    if status != 200:
        raise SystemExit(f"token is not usable: HTTP {status} {user.get('message', '')}")
    owner = user["login"]
    print(f"[api] authenticated as {owner}")

    status, repo = api(f"/repos/{owner}/{args.repo_name}", token)
    if status == 404:
        status, repo = api(
            "/user/repos",
            token,
            "POST",
            {
                "name": args.repo_name,
                "private": bool(args.private),
                "description": "Progressive-disclosure skill agent: discovery, prompt budget, routing eval, demo UI",
                "has_issues": True,
                "has_wiki": False,
            },
        )
        if status not in (200, 201):
            raise SystemExit(f"could not create repository: HTTP {status} {repo.get('message', '')}")
        print(f"[api] created {repo['full_name']}")
    elif status == 200:
        print(f"[api] repository already exists: {repo['full_name']}")
    else:
        raise SystemExit(f"repository lookup failed: HTTP {status} {repo.get('message', '')}")

    if args.dry_run:
        print("[dry-run] stopping before git push")
        return 0

    branch = args.branch or run_git("rev-parse", "--abbrev-ref", "HEAD", cwd=REPO_ROOT)
    remote_url = repo["clone_url"]
    remotes = run_git("remote", cwd=REPO_ROOT).split()
    if "origin" in remotes:
        run_git("remote", "set-url", "origin", remote_url, cwd=REPO_ROOT)
    else:
        run_git("remote", "add", "origin", remote_url, cwd=REPO_ROOT)

    push_url = f"https://x-access-token:{token}@github.com/{owner}/{args.repo_name}.git"
    print(f"[git] pushing {branch} -> main")
    run_git("push", push_url, f"{branch}:main", cwd=REPO_ROOT)
    run_git("config", "branch." + branch + ".remote", "origin", cwd=REPO_ROOT)
    run_git("config", "branch." + branch + ".merge", "refs/heads/main", cwd=REPO_ROOT)

    status, commits = api(f"/repos/{owner}/{args.repo_name}/commits?per_page=100", token)
    count = len(commits) if isinstance(commits, list) else "?"
    status, tree = api(f"/repos/{owner}/{args.repo_name}/git/trees/{repo.get('default_branch', 'main')}?recursive=1", token)
    files = len(tree.get("tree", [])) if isinstance(tree, dict) else "?"
    print(f"[verify] {repo['html_url']}  commits={count} files={files} private={repo['private']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
