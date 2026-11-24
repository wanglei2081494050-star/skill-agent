"""Bulk skill simulation for the "simulate 200 skills" debug switch.

The generated skills are *not* written to disk: the demo needs to show how the
injected skill section stays inside its budget when the catalogue is large, and
writing 200 directories would pollute the repo. They are synthesized in memory
and merged into the snapshot for prompt building only.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from .config import REPO_ROOT
from .skills import Skill
from .tokens import estimate_tokens

TOPICS = [
    ("invoice", "发票开具与红冲流程"),
    ("payroll", "薪资核算与个税申报"),
    ("onboarding", "新员工入职材料收集"),
    ("churn", "流失用户回访话术"),
    ("sla", "服务等级协议核算"),
    ("seo", "站点关键词与落地页优化"),
    ("ab-test", "灰度实验设计与显著性判断"),
    ("i18n", "多语言文案校对"),
    ("audit", "审计日志字段对齐"),
    ("backup", "备份与恢复演练"),
    ("incident", "线上故障复盘报告"),
    ("pricing", "定价方案对比测算"),
    ("contract", "合同条款风险标注"),
    ("recruit", "岗位 JD 撰写"),
    ("qa", "客服知识库答疑"),
    ("forecast", "销量预测与补货"),
    ("logistics", "物流时效异常排查"),
    ("tax", "跨境税务合规检查"),
    ("security", "权限最小化审计"),
    ("migration", "数据库迁移窗口评估"),
]


class BulkCatalog:
    """Deterministic generator of extra skills."""

    def __init__(self, count: int = 200) -> None:
        self.count = count
        self._cache: dict[int, list[Skill]] = {}

    def skills(self, count: int | None = None) -> list[Skill]:
        count = self.count if count is None else count
        if count in self._cache:
            return self._cache[count]
        out: list[Skill] = []
        for idx in range(count):
            topic, label = TOPICS[idx % len(TOPICS)]
            round_no = idx // len(TOPICS) + 1
            name = f"sim-{topic}-{round_no:02d}"
            description = (
                f"{label}（模拟技能 {idx + 1}/{count}）：按标准流程收集输入、核对关键字段、"
                "输出结论与待办，并在缺少信息时明确列出需要补充的材料。"
            )
            body = (
                f"# {name}\n\nSimulated skill used only to stress the prompt budget.\n\n"
                f"1. Confirm inputs for: {label}.\n2. Check the two key fields.\n"
                "3. Output the result and the follow-up list.\n"
            )
            fake_dir = Path(REPO_ROOT) / "skills" / ".simulated" / name
            out.append(
                Skill(
                    name=name,
                    description=description,
                    source_id="simulated",
                    source_label="Simulated (200)",
                    priority=0,
                    dir=fake_dir,
                    body=body,
                    meta={"name": name, "description": description},
                    attached=[],
                    depends_on=[],
                    line_tokens=estimate_tokens(f"{name}: {description}"),
                    body_tokens=estimate_tokens(body),
                    mtime_ns=int(hashlib.sha256(name.encode()).hexdigest()[:8], 16),
                )
            )
        self._cache[count] = out
        return out


BULK = BulkCatalog()
