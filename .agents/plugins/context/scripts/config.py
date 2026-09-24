# ruff: noqa: INP001  # standalone script, not a package
"""Where a repository keeps its agent guidance, read from .claude/context.md and .claude/context.local.md.

Both files hold YAML frontmatter with the keys in KEYS, each a list of repo-relative globs or directories.
The local file is meant to stay out of git and replaces whole keys. Globs match paths after symlinks
resolve, the way the tracker records them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

CONFIG_FILES = (".claude/context.md", ".claude/context.local.md")
KEYS = ("docs", "also_logged", "working_files", "skill_dirs", "skip_dirs")
DEFAULTS: dict[str, tuple[str, ...]] = {
    "docs": ("**/AGENTS.md", "**/CLAUDE.md"),
    "also_logged": (".claude/**",),
    "working_files": (),
    "skill_dirs": (),
    "skip_dirs": (),
}


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Translate a rule's `paths:` glob, where `**` spans directories and `*` does not."""
    parts = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            parts.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            parts.append(".*")
            i += 2
        elif pattern[i] == "*":
            parts.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            parts.append("[^/]")
            i += 1
        else:
            parts.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(parts) + r"\Z")


@cache
def compiled(pattern: str) -> re.Pattern[str]:
    return glob_to_regex(pattern)


def matches(rel: str, patterns: tuple[str, ...]) -> bool:
    return any(compiled(pattern).match(rel) for pattern in patterns)


def in_dir(rel: str, directory: str) -> bool:
    return rel == directory or rel.startswith(directory.rstrip("/") + "/")


def unquote(value: str) -> str:
    return value.strip().strip("\"'")


def frontmatter_lists(text: str) -> dict[str, list[str]]:
    """Top-level keys of a leading YAML frontmatter block, each as a list of strings; a scalar is one item.

    Raises:
        ValueError: On a line that is neither `key: value`, `key: [a, b]`, `key:` nor a `- item` under a key.

    """
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    values: dict[str, list[str]] = {}
    key = None
    for line in text[4 : end if end != -1 else 4].splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[0].isspace():
            item = re.match(r"\s*-\s*(.+)$", line)
            if key is None or item is None:
                raise ValueError(f"cannot read frontmatter line {line!r}")
            values[key].append(unquote(item.group(1)))
            continue
        name, separator, rest = line.partition(":")
        if not separator:
            raise ValueError(f"cannot read frontmatter line {line!r}")
        key, rest = name.strip(), rest.strip()
        if rest.startswith("[") and rest.endswith("]"):
            values[key] = [unquote(value) for value in rest[1:-1].split(",") if value.strip()]
        else:
            values[key] = [unquote(rest)] if rest else []
    return values


@dataclass(frozen=True)
class Layout:
    docs: tuple[str, ...]
    """Guidance: every Read of these is logged, and the doctor reads them all."""

    also_logged: tuple[str, ...]
    """Reads of these are logged too, but they are not guidance the doctor reads (commands, rules, skills)."""

    working_files: tuple[str, ...]
    """Material a session works on, such as spec artifacts: logged, but never read or judged as guidance."""

    skill_dirs: tuple[str, ...]
    """Skill directories Claude Code does not load itself: indexed, not read."""

    skip_dirs: tuple[str, ...]
    """Directories never scanned, such as submodules."""

    sources: tuple[str, ...]
    """The config files the values came from; empty when the defaults apply."""

    def is_logged(self, rel: str) -> bool:
        return matches(rel, self.docs + self.also_logged + self.working_files)

    def is_working_file(self, rel: str) -> bool:
        return matches(rel, self.working_files)

    def is_doc(self, rel: str) -> bool:
        return (
            matches(rel, self.docs)
            and not self.is_working_file(rel)
            and not any(in_dir(rel, directory) for directory in self.skill_dirs)
        )

    def describe(self) -> str:
        fields = " · ".join(f"{key.replace('_', ' ')}: {', '.join(getattr(self, key)) or 'none'}" for key in KEYS)
        return f"{fields} (from {', '.join(self.sources) or 'the plugin defaults: no .claude/context.md'})"


def load_layout(project: Path) -> Layout:
    """The project's layout: the defaults, then .claude/context.md, then .claude/context.local.md.

    Raises:
        ValueError: When a config file cannot be read or names a key outside KEYS.

    """
    values = dict(DEFAULTS)
    sources = []
    for name in CONFIG_FILES:
        path = project / name
        if not path.is_file():
            continue
        try:
            found = frontmatter_lists(path.read_text(encoding="utf-8"))
        except ValueError as error:
            raise ValueError(f"{path}: {error}") from error
        if unknown := sorted(set(found) - set(KEYS)):
            raise ValueError(f"{path}: unknown keys {', '.join(unknown)}; expected {', '.join(KEYS)}")
        values.update({key: tuple(found[key]) for key in found})
        sources.append(name)
    return Layout(**values, sources=tuple(sources))
