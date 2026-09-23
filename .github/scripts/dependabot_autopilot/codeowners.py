"""Resolve the owners of changed paths from a CODEOWNERS file, following GitHub's matching rules."""

from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import takewhile
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable


@dataclass(frozen=True)
class _Rule:
    pattern: re.Pattern[str]
    owners: tuple[str, ...]
    """Empty for a rule that leaves its paths without an owner."""


def owners_for(*, paths: Iterable[str], codeowners_text: str, fallback: str) -> tuple[str, ...]:
    """Return, sorted, the owners of every path, or `(fallback,)` when no path has an owner.

    For each path the last matching rule decides its owners.
    """
    rules = _parse(text=codeowners_text)
    owners = {owner for path in paths for owner in _path_owners(path=path.lstrip("/"), rules=rules)}
    return tuple(sorted(owners)) if owners else (fallback,)


def _path_owners(*, path: str, rules: list[_Rule]) -> tuple[str, ...]:
    for rule in reversed(rules):
        if rule.pattern.fullmatch(path):
            return rule.owners
    return ()


def _parse(*, text: str) -> list[_Rule]:
    rules = []
    for line in text.splitlines():
        stripped = line.lstrip()
        # GitHub does not honour a backslash escaping a leading `#`, so such a line never assigns owners.
        if not stripped or stripped.startswith(("#", "\\#")):
            continue
        pattern, *fields = _tokenize(line=stripped)
        owners = list(takewhile(lambda field: not field.startswith("#"), fields))
        rules.append(_Rule(pattern=_compile(pattern=pattern), owners=tuple(owners)))
    return rules


def _tokenize(*, line: str) -> list[str]:
    """Split on whitespace not escaped by a backslash, keeping the escapes in each token."""
    tokens: list[str] = []
    current = ""
    characters = iter(line)
    for character in characters:
        if character == "\\":
            current += character + next(characters, "")
        elif character.isspace():
            if current:
                tokens.append(current)
            current = ""
        else:
            current += character
    return [*tokens, current] if current else tokens


def _compile(*, pattern: str) -> re.Pattern[str]:
    directory_only = pattern.endswith("/")
    body = pattern.rstrip("/")
    anchored = "/" in body
    body = body.lstrip("/")
    prefix = "" if anchored else "(?:.*/)?"
    if directory_only:
        suffix = "/.*"
    elif body.rpartition("/")[2] == "*":
        suffix = ""
    else:
        suffix = "(?:/.*)?"
    return re.compile(prefix + _translate(glob=body) + suffix)


def _translate(*, glob: str) -> str:
    parts: list[str] = []
    index = 0
    while index < len(glob):
        if glob.startswith("**/", index):
            parts.append("(?:.*/)?")
            index += 3
        elif glob.startswith("**", index):
            parts.append(".*")
            index += 2
        elif glob[index] == "*":
            parts.append("[^/]*")
            index += 1
        elif glob[index] == "?":
            parts.append("[^/]")
            index += 1
        elif glob[index] == "\\":
            parts.append(re.escape(glob[index + 1 : index + 2] or "\\"))
            index += 2
        else:
            parts.append(re.escape(glob[index]))
            index += 1
    return "".join(parts)
