"""System-prompt injection: build the skill section and keep it inside budget.

The injected section is *only* names and one-line descriptions; bodies stay on
disk until the model asks for one. When the skill set grows the section must not
grow linearly, so the builder degrades in four levels:

    full      - every line verbatim
    compact   - description truncated to DESCRIPTION_TRUNCATE_CHARS
    tight     - description truncated to MIN_DESCRIPTION_CHARS
    truncated - drop lowest-priority skills until the budget fits, and append a
                "... N more skills not listed, ask for a name" line

The same policy is what the demo shows when the "simulate 200 skills" switch is
on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .config import (
    DESCRIPTION_TRUNCATE_CHARS,
    MIN_DESCRIPTION_CHARS,
    PROMPT_BUDGET_TOKENS,
)
from .skills import Skill, Snapshot
from .tokens import estimate_tokens

HEADER = (
    "## Skills\n"
    "Skills are capability packs. Only the name and description are visible here.\n"
    "Call load_skill(name) to read the full body before acting, and read_skill_file(name, path)\n"
    "for any attached file the body references. Do not guess a skill's steps from its description.\n"
)


def _skill_line(skill: Skill, desc_chars: int | None, marker: str = "") -> str:
    desc = skill.description
    if desc_chars is not None and len(desc) > desc_chars:
        desc = desc[: max(1, desc_chars - 1)].rstrip() + "…"
    prefix = f"- {skill.name}" if not marker else f"- {skill.name} [{marker}]"
    return f"{prefix}: {desc}"


@dataclass
class PromptBuild:
    text: str
    tokens: int
    level: str
    budget: int
    included: list[str] = field(default_factory=list)
    omitted: list[str] = field(default_factory=list)
    per_skill_tokens: dict[str, int] = field(default_factory=dict)

    def summary(self) -> dict[str, Any]:
        return {
            "tokens": self.tokens,
            "budget": self.budget,
            "level": self.level,
            "included": self.included,
            "omitted": self.omitted,
            "perSkillTokens": self.per_skill_tokens,
            "text": self.text,
        }


def build_skill_section(
    snapshot: Snapshot,
    budget: int = PROMPT_BUDGET_TOKENS,
    extra_skills: list[Skill] | None = None,
) -> PromptBuild:
    """Return the injected skill section, degraded to fit ``budget`` tokens."""
    skills: list[Skill] = list(snapshot.skills)
    if extra_skills:
        skills.extend(extra_skills)

    trials: list[tuple[str, int | None]] = [
        ("full", None),
        ("compact", DESCRIPTION_TRUNCATE_CHARS),
        ("tight", MIN_DESCRIPTION_CHARS),
    ]
    for level, desc_chars in trials:
        lines = [_skill_line(s, desc_chars) for s in skills]
        text = HEADER + "\n".join(lines)
        tokens = estimate_tokens(text)
        if tokens <= budget:
            return PromptBuild(
                text=text,
                tokens=tokens,
                level=level,
                budget=budget,
                included=[s.name for s in skills],
                per_skill_tokens={s.name: estimate_tokens(l) for s, l in zip(skills, lines)},
            )

    # Level 4: keep as many as fit, lowest priority dropped first. ``skills`` is
    # already ordered by descending priority, so we cut from the tail.
    desc_chars = MIN_DESCRIPTION_CHARS
    keep = len(skills)
    while keep > 0:
        kept = skills[:keep]
        dropped = skills[keep:]
        lines = [_skill_line(s, desc_chars) for s in kept]
        footer = (
            f"\n- ({len(dropped)} more skills exist but are not listed to save tokens; "
            "ask the operator for a name if needed.)"
            if dropped
            else ""
        )
        text = HEADER + "\n".join(lines) + footer
        tokens = estimate_tokens(text)
        if tokens <= budget:
            return PromptBuild(
                text=text,
                tokens=tokens,
                level="truncated",
                budget=budget,
                included=[s.name for s in kept],
                omitted=[s.name for s in dropped],
                per_skill_tokens={s.name: estimate_tokens(l) for s, l in zip(kept, lines)},
            )
        keep -= 1

    text = HEADER + "- (skill list omitted: budget too small to list any skill.)"
    minimal_candidates = [
        HEADER + f"- {len(skills)} skills exist; list omitted for budget.",
        f"## Skills\n- {len(skills)} skills exist; wall of names omitted to save tokens.",
        f"## Skills\n- {len(skills)} skills hidden by budget.",
        "## Skills\n- hidden by budget.",
        "- skills hidden.",
    ]
    for candidate in minimal_candidates:
        if estimate_tokens(candidate) <= budget:
            text = candidate
            break
    else:
        # Last resort: hard-clip characters until the estimate fits.
        clipped = minimal_candidates[-1]
        while clipped and estimate_tokens(clipped) > budget:
            clipped = clipped[:-1]
        text = clipped or "x"[:budget]
    return PromptBuild(
        text=text,
        tokens=estimate_tokens(text),
        level="truncated",
        budget=budget,
        included=[],
        omitted=[s.name for s in skills],
    )
