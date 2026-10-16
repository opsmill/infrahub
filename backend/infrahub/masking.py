"""Rules that mask personal data and secrets in span attributes and log fields.

This module has no third-party dependencies, so that logging can use it without importing the tracing exporters.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

MASKED_VALUE = "[MASKED]"

# A URL with a scheme, followed by its query string; both end at a space, a quote or an angle bracket.
_URL_WITH_QUERY = re.compile(r"(?P<base>\b[a-zA-Z][a-zA-Z0-9+.-]*://[^\s?'\"<>`]*)\?[^\s'\"<>`]*")


def replace_value(value: Any) -> str:  # noqa: ARG001
    return MASKED_VALUE


def replace_url_query(value: Any) -> Any:
    if not isinstance(value, str):
        return MASKED_VALUE
    base, separator, _ = value.partition("?")
    if not separator:
        return value
    return f"{base}?{MASKED_VALUE}"


def replace_url_queries_in_text(text: str) -> str:
    """Return `text` with the query string of every URL in it replaced, keeping the scheme, host, path and other text."""
    return _URL_WITH_QUERY.sub(lambda match: f"{match.group('base')}?{MASKED_VALUE}", text)


@dataclass(frozen=True)
class MaskingRule:
    """Mask a value whose key is one of `keys`, or whose lower-case key contains one of `key_fragments`."""

    mask: Callable[[Any], Any]
    keys: frozenset[str] = frozenset()
    key_fragments: frozenset[str] = frozenset()

    def applies_to(self, key: str) -> bool:
        if key in self.keys:
            return True
        lower_key = key.lower()
        return any(fragment in lower_key for fragment in self.key_fragments)


MASKING_RULES: tuple[MaskingRule, ...] = (
    MaskingRule(keys=frozenset({"net.peer.ip", "client.address", "client_ip"}), mask=replace_value),
    MaskingRule(keys=frozenset({"http.url", "http.target", "url.full", "url"}), mask=replace_url_query),
    MaskingRule(keys=frozenset({"url.query", "account_name"}), mask=replace_value),
    MaskingRule(
        key_fragments=frozenset({"token", "password", "secret", "email", "user_name", "username"}),
        mask=replace_value,
    ),
)


def mask_value(key: str, value: Any, rules: Sequence[MaskingRule] = MASKING_RULES) -> Any:
    """Return `value` masked by the first rule that applies to `key`, or `value` itself when none applies."""
    for rule in rules:
        if rule.applies_to(key):
            return rule.mask(value)
    return value


def mask_nested(value: Any, rules: Sequence[MaskingRule] = MASKING_RULES) -> Any:
    """Return a copy of `value` with the values of matching keys masked at every level of its mappings and lists.

    A copy is returned, because the caller may still use the mapping it passed to the logger.
    """
    if isinstance(value, Mapping):
        return mask_mapping(data=value, rules=rules)
    if isinstance(value, list | tuple):
        return type(value)(mask_nested(value=item, rules=rules) for item in value)
    return value


def mask_mapping(data: Mapping[str, Any], rules: Sequence[MaskingRule] = MASKING_RULES) -> dict[str, Any]:
    masked: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(key, str) and any(rule.applies_to(key) for rule in rules):
            masked[key] = mask_value(key=key, value=value, rules=rules)
        else:
            masked[key] = mask_nested(value=value, rules=rules)
    return masked
