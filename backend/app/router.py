"""Deterministic skill router used for the offline path and for the eval harness.

The router is a small BM25-flavoured scorer, not a model:

* tokens: latin words (len >= 2) plus CJK character bigrams
* doc: ``name + " " + description`` of each skill
* idf: computed over the whole skill set, so a token that appears in every
  description contributes almost nothing - this is exactly why the two
  confusable drama skills collide before their descriptions are disambiguated
* score: sum(idf * (1 + 0.5 if the token also appears in the name))
* route: best score must clear ``threshold``, otherwise "no skill"

It is deterministic, costs nothing, and makes the description-tuning experiment
reproducible without an API key.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Iterable

from .skills import Skill

CJK_RUN = re.compile(r"[\u4e00-\u9fff]+")
LATIN_WORD = re.compile(r"[a-z0-9][a-z0-9_-]+")

DEFAULT_THRESHOLD = 1.6


def tokens(text: str) -> list[str]:
    text = text.lower()
    out: list[str] = []
    for run in CJK_RUN.findall(text):
        if len(run) == 1:
            out.append(run)
        out.extend(run[i : i + 2] for i in range(len(run) - 1))
    out.extend(LATIN_WORD.findall(text))
    return out


@dataclass
class SkillDoc:
    name: str
    name_tokens: set[str]
    desc_tokens: list[str]
    description: str

    @classmethod
    def from_skill(cls, skill: Skill, description: str | None = None) -> "SkillDoc":
        desc = skill.description if description is None else description
        return cls(
            name=skill.name,
            name_tokens=set(tokens(skill.name)),
            desc_tokens=tokens(desc),
            description=desc,
        )


def _idf_map(docs: Iterable[SkillDoc]) -> dict[str, float]:
    docs = list(docs)
    n = max(1, len(docs))
    df: dict[str, int] = {}
    for doc in docs:
        for tok in set(doc.desc_tokens) | doc.name_tokens:
            df[tok] = df.get(tok, 0) + 1
    return {tok: math.log(1 + n / (1 + count)) for tok, count in df.items()}


def score_docs(query: str, docs: list[SkillDoc]) -> list[tuple[str, float]]:
    idf = _idf_map(docs)
    query_tokens = set(tokens(query))
    scores: list[tuple[str, float]] = []
    for doc in docs:
        desc_set = set(doc.desc_tokens)
        score = 0.0
        for tok in query_tokens:
            if tok in desc_set or tok in doc.name_tokens:
                weight = idf.get(tok, 1.0)
                if tok in doc.name_tokens:
                    weight *= 1.5
                score += weight
        scores.append((doc.name, round(score, 4)))
    scores.sort(key=lambda item: (-item[1], item[0]))
    return scores


def route(
    query: str,
    skills: list[Skill],
    threshold: float = DEFAULT_THRESHOLD,
    descriptions: dict[str, str] | None = None,
) -> dict[str, Any]:
    descriptions = descriptions or {}
    docs = [SkillDoc.from_skill(s, descriptions.get(s.name)) for s in skills]
    scores = score_docs(query, docs)
    best_name, best_score = scores[0] if scores else (None, 0.0)
    chosen = best_name if best_score >= threshold else None
    return {
        "query": query,
        "skill": chosen,
        "score": best_score,
        "threshold": threshold,
        "top": scores[:5],
    }
