# ruff: noqa: S101, INP001
from __future__ import annotations

import re
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2] / "skills" / "reviewing-changes"


def test_every_reference_file_is_listed_and_exists() -> None:
    skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    table = skill.split("## Files of this skill", 1)[1].split("\n## ", 1)[0]
    listed = set(re.findall(r"^\| `(references/[\w-]+\.md)` \|", table, flags=re.MULTILINE))
    on_disk = {f"references/{path.name}" for path in (SKILL_DIR / "references").glob("*.md")}
    named = set(re.findall(r"`(references/[\w-]+\.md)`", skill))

    assert listed == on_disk
    assert named <= on_disk
