# ruff: noqa: INP001  # standalone script, not a package
"""Where a repository keeps its agent guidance, read from context.md in .agents/ or .claude/.

The file holds YAML frontmatter with the keys in KEYS, each a list of repo-relative globs or directories.
A repository that uses both folders keeps one file and symlinks the other name to it. A context.local.md
in either folder is meant to stay out of git and replaces whole keys. Globs match paths after symlinks
resolve, the way the tracker records them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

PROJECT_FILES = (".agents/context.md", ".claude/context.md")
LOCAL_FILES = (".agents/context.local.md", ".claude/context.local.md")
KEYS = ("docs", "also_logged", "working_files", "skip_dirs", "lint_allow")
DEFAULTS: dict[str, tuple[str, ...]] = {
    "docs": ("**/AGENTS.md", "**/CLAUDE.md"),
    "also_logged": (".agents/**", ".claude/**"),
    "working_files": (),
    "skip_dirs": (),
    "lint_allow": (),
}


def glob_source(pattern: str) -> str:
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
        elif pattern[i] == "{" and (close := pattern.find("}", i)) != -1:
            options = pattern[i + 1 : close].split(",")
            parts.append("(?:" + "|".join(glob_source(option) for option in options) + ")")
            i = close + 1
        else:
            parts.append(re.escape(pattern[i]))
            i += 1
    return "".join(parts)


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Translate a glob where `**` spans directories, `*` does not, and `{a,b}` lists alternatives."""
    return re.compile(glob_source(pattern) + r"\Z")


@cache
def compiled(pattern: str) -> re.Pattern[str]:
    return glob_to_regex(pattern)


def is_instruction_file(rel: str) -> bool:
    """CLAUDE.md and AGENTS.md files are guidance in every repository, whatever the config lists."""
    return rel.rsplit("/", 1)[-1] in {"CLAUDE.md", "AGENTS.md"}


def matches(rel: str, patterns: tuple[str, ...]) -> bool:
    return any(compiled(pattern).match(rel) for pattern in patterns)


def unquote(value: str) -> str:
    return value.strip().strip("\"'")


def frontmatter_lists(text: str, *, strict: bool = True) -> dict[str, list[str]]:
    """Top-level keys of a leading YAML frontmatter block, each as a list of strings; a scalar is one item.

    Without strict, lines it cannot read are skipped, for frontmatter that holds richer YAML too.

    Raises:
        ValueError: In strict mode, on a line that is neither `key: value`, `key: [a, b]`, `key:` nor a
            `- item` under a key.

    """
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    values: dict[str, list[str]] = {}
    key = None
    for raw in text[4 : end if end != -1 else 4].splitlines():
        # A YAML comment starts at a # after whitespace, outside quotes.
        line = re.sub(r"\s+#[^\"']*$", "", raw)
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[0].isspace():
            item = re.match(r"\s*-\s*(.+)$", line)
            if key is None or item is None:
                if strict:
                    raise ValueError(f"cannot read frontmatter line {raw!r}")
                continue
            values[key].append(unquote(item.group(1)))
            continue
        name, separator, rest = line.partition(":")
        if not separator:
            if strict:
                raise ValueError(f"cannot read frontmatter line {raw!r}")
            key = None
            continue
        key, rest = name.strip(), rest.strip()
        if rest.startswith("[") and rest.endswith("]"):
            values[key] = [unquote(value) for value in rest[1:-1].split(",") if value.strip()]
        else:
            values[key] = [unquote(rest)] if rest else []
    return values


def rule_patterns(text: str) -> list[str]:
    """Return a rule's `paths:` globs; an empty list means the rule loads at startup."""
    return frontmatter_lists(text, strict=False).get("paths", [])


@dataclass(frozen=True)
class Layout:
    docs: tuple[str, ...]
    """Guidance: every Read of these is logged, and the doctor reads them all."""

    also_logged: tuple[str, ...]
    """Reads of these are logged too, but they are not guidance the doctor reads (commands, rules, skills)."""

    working_files: tuple[str, ...]
    """Material a session works on, such as spec artifacts: logged, but never read or judged as guidance."""

    skip_dirs: tuple[str, ...]
    """Directories never scanned, such as submodules."""

    sources: tuple[str, ...]
    """The config files the values came from; empty when the defaults apply."""

    lint_allow: tuple[str, ...] = ()
    """Files allowed to name harness-loaded files by path, such as guidance about writing guidance."""

    def is_logged(self, rel: str) -> bool:
        return is_instruction_file(rel) or matches(rel, self.docs + self.also_logged + self.working_files)

    def is_working_file(self, rel: str) -> bool:
        return matches(rel, self.working_files)

    def is_doc(self, rel: str) -> bool:
        return (is_instruction_file(rel) or matches(rel, self.docs)) and not self.is_working_file(rel)

    def allows_references(self, rel: str) -> bool:
        return matches(rel, self.lint_allow)

    def describe(self) -> str:
        fields = " · ".join(f"{key.replace('_', ' ')}: {', '.join(getattr(self, key)) or 'none'}" for key in KEYS)
        source = (
            ", ".join(self.sources) or "the plugin defaults: no context.md in .agents/ or .claude/, see /context:init"
        )
        return f"{fields} (from {source})"


def find_config(project: Path, names: tuple[str, ...]) -> str | None:
    """The config file among names that exists, counting a symlink and its target as one file.

    Raises:
        ValueError: When two of them exist as separate files.

    """
    found: dict[Path, str] = {}
    for name in names:
        if (project / name).is_file():
            found.setdefault((project / name).resolve(), name)
    if len(found) > 1:
        raise ValueError(
            f"{' and '.join(found.values())} are separate files; keep one and make the other a symlink to it, "
            "for example: ln -s ../.agents/context.md .claude/context.md"
        )
    return next(iter(found.values()), None)


def load_layout(project: Path) -> Layout:
    """The project's layout: the defaults, then its context.md, then its context.local.md.

    Raises:
        ValueError: When a config file cannot be read, names a key outside KEYS, or exists twice.

    """
    values = dict(DEFAULTS)
    sources = []
    for names in (PROJECT_FILES, LOCAL_FILES):
        name = find_config(project, names)
        if name is None:
            continue
        path = project / name
        try:
            found = frontmatter_lists(path.read_text(encoding="utf-8"))
        except ValueError as error:
            raise ValueError(f"{path}: {error}") from error
        if unknown := sorted(set(found) - set(KEYS)):
            raise ValueError(f"{path}: unknown keys {', '.join(unknown)}; expected {', '.join(KEYS)}")
        values.update({key: tuple(found[key]) for key in found})
        sources.append(name)
    return Layout(**values, sources=tuple(sources))
