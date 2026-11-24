"""Static configuration for the skill agent (paths, budgets, pricing)."""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_ROOT = REPO_ROOT / "skills"
DATA_DIR = REPO_ROOT / "data"
EVAL_CASES_PATH = REPO_ROOT / "eval" / "routing_cases.json"
EVAL_REPORT_DIR = REPO_ROOT / "data" / "eval"

# Ordered skill sources. Higher ``priority`` wins when two sources provide the
# same skill name; the loser is reported as ``shadowed`` in the UI.
DEFAULT_SOURCES = [
    {"id": "builtin", "label": "Built-in", "path": "skills/builtin", "priority": 10},
    {"id": "team", "label": "Team shared", "path": "skills/team", "priority": 20},
    {"id": "personal", "label": "Personal", "path": "skills/personal", "priority": 30},
]

# Hard cap for the skill section that is concatenated into the system prompt.
PROMPT_BUDGET_TOKENS = int(os.environ.get("PROMPT_BUDGET_TOKENS", "800"))
# When the budget is exceeded: first shrink every description to this many
# characters, then drop the lowest-priority trailing skills if still over.
DESCRIPTION_TRUNCATE_CHARS = int(os.environ.get("DESCRIPTION_TRUNCATE_CHARS", "160"))
MIN_DESCRIPTION_CHARS = 48

# Upper bound for a single attached file read by read_skill_file.
MAX_ATTACHED_FILE_BYTES = 64 * 1024
MAX_ATTACHED_FILES_PER_SKILL = 40

# Script sandbox limits.
SCRIPT_TIMEOUT_SECONDS = float(os.environ.get("SCRIPT_TIMEOUT_SECONDS", "10"))
SCRIPT_MAX_OUTPUT_BYTES = 8 * 1024

# LLM provider (OpenAI compatible). Without a key the agent falls back to the
# deterministic offline router, and the trace marks mode="offline".
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "deepseek-chat")
LLM_API_KEY = os.environ.get("LLM_API_KEY") or os.environ.get("DEEPSEEK_API_KEY") or ""
LLM_TIMEOUT_SECONDS = float(os.environ.get("LLM_TIMEOUT_SECONDS", "60"))
# USD per 1M tokens; defaults are the published deepseek-chat cache-miss price.
PRICE_INPUT_PER_M = float(os.environ.get("PRICE_INPUT_PER_M", "0.27"))
PRICE_OUTPUT_PER_M = float(os.environ.get("PRICE_OUTPUT_PER_M", "1.10"))

MAX_TOOL_ROUNDS = 4
