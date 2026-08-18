"""Guards the hex-suffix invariant that keeps branch names from colliding with locators.

Prose alone already failed once: this helper and its TypeScript counterpart silently diverged
despite documenting themselves as ports of each other, which is how a base36 alphabet survived
long enough to spell "save" in a branch name and match ``getByRole("button", {name: "Save"})``.

Nothing here needs a browser or a running Infrahub, but it still lives in this suite because it is
the only place the helper is importable. Two consequences: it carries a shard marker, since CI
selects with ``-m shard_<name>`` and an unmarked test is deselected in every shard; and it inherits
the suite's stack, because pytest-base-url's autouse ``_verify_url`` pulls in ``base_url`` and the
conftest points that at the compose stack. Free in CI, where the stack is already up.
"""

from __future__ import annotations

import re

import pytest
from helpers import generate_random_branch_name

pytestmark = pytest.mark.shard_foundation

HEX_SUFFIX = re.compile(r"[0-9a-f]{12}")
SAMPLE_SIZE = 1000


def test_suffixes_a_prefix_with_hex_only() -> None:
    prefix = "object-relationships"

    suffixes = [generate_random_branch_name(prefix).removeprefix(prefix) for _ in range(SAMPLE_SIZE)]

    assert [suffix for suffix in suffixes if not HEX_SUFFIX.fullmatch(suffix)] == []


def test_returns_hex_only_when_no_prefix_is_given() -> None:
    names = [generate_random_branch_name() for _ in range(SAMPLE_SIZE)]

    assert [name for name in names if not HEX_SUFFIX.fullmatch(name)] == []
