"""A `ClaimFilter` decides which external IdP group claims become local groups, and how to
name them.

Patterns are tried in declared order. The first match per claim wins; subsequent patterns are
not consulted for that claim. A pattern with a named capture group `(?P<name>...)` yields the
captured value as the local group name; otherwise the full claim string is used. Positional
capture groups are not used for name extraction.

Compiled `re.Pattern` objects are produced by
`SecuritySettings._compile_auto_create_groups_filter_patterns` at config load time, so by the
time the filter is exercised here every pattern is known to compile.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    import re


class ClaimFilter:
    """A filter that derives local group names from external IdP claims."""

    def __init__(self, patterns: tuple[re.Pattern[str], ...]) -> None:
        self._patterns = patterns

    @property
    def is_active(self) -> bool:
        return len(self._patterns) > 0

    def name_for(self, claim: str) -> str | None:
        """The local group name for `claim`, or `None` if no pattern matches."""
        for pattern in self._patterns:
            match = pattern.search(claim)
            if match is None:
                continue
            named = match.groupdict()
            if "name" in named and named["name"] is not None:
                return named["name"]
            return claim
        return None

    def names_for(self, claims: Iterable[str]) -> tuple[str, ...]:
        """The local group names for `claims`, in matching order, with duplicates collapsed."""
        seen: set[str] = set()
        out: list[str] = []
        for claim in claims:
            name = self.name_for(claim)
            if name is None or name in seen:
                continue
            seen.add(name)
            out.append(name)
        return tuple(out)
