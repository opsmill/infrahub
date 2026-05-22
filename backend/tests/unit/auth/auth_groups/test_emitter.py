"""Unit tests for helpers in `infrahub.auth.auth_groups.emitter`.

Locks in the boundary semantics of `_truncate` around `MAX_CLAIM_VALUE_LENGTH`:
inputs at or below the limit pass through unchanged; inputs above are sliced to
exactly the limit. Guards against an accidental `<` vs `<=` flip in the
truncation guard.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from infrahub.auth.auth_groups.emitter import MAX_CLAIM_VALUE_LENGTH, _truncate


@dataclass(frozen=True)
class TruncateCase:
    name: str
    value: str
    expected: str


@pytest.mark.parametrize(
    "case",
    [
        TruncateCase(name="empty", value="", expected=""),
        TruncateCase(name="below_limit", value="x" * 100, expected="x" * 100),
        TruncateCase(
            name="exactly_at_limit",
            value="x" * MAX_CLAIM_VALUE_LENGTH,
            expected="x" * MAX_CLAIM_VALUE_LENGTH,
        ),
        TruncateCase(
            name="one_over_limit",
            value="x" * (MAX_CLAIM_VALUE_LENGTH + 1),
            expected="x" * MAX_CLAIM_VALUE_LENGTH,
        ),
    ],
    ids=lambda case: case.name,
)
def test_truncate_boundaries(case: TruncateCase) -> None:
    assert _truncate(case.value) == case.expected
