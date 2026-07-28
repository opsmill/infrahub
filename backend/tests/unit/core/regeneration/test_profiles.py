from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.regeneration.profiles import SchemaProfileExpander
from infrahub.core.schema.manager import SchemaManager
from infrahub.core.schema.schema_branch import SchemaBranch
from tests.helpers.merge_recompute.dataset import PROFILE_NODE_KIND, build_profile_schema

if TYPE_CHECKING:
    from collections.abc import Generator

BRANCH = "test-profile-expander"
PROFILE_KIND = f"Profile{PROFILE_NODE_KIND}"


@pytest.fixture
def profile_schema_registered() -> Generator[None, None, None]:
    """Register a schema branch that generates profiles, so the expander can resolve them by branch."""
    original = registry._schema
    manager = SchemaManager()
    schema_branch = SchemaBranch(cache={}, name=BRANCH)
    schema_branch.load_schema(schema=build_profile_schema())
    schema_branch.process()
    manager.set_schema_branch(name=BRANCH, schema=schema_branch)
    registry.schema = manager
    yield
    registry._schema = original


@dataclass(frozen=True, kw_only=True)
class ExpandCase:
    name: str
    modified_kinds: list[str]
    expected: set[str]


EXPAND_CASES = [
    ExpandCase(
        name="profile_kind_widens_to_its_node_kind",
        modified_kinds=[PROFILE_KIND],
        expected={PROFILE_KIND, PROFILE_NODE_KIND},
    ),
    ExpandCase(
        name="non_profile_kinds_pass_through_unchanged",
        modified_kinds=[PROFILE_NODE_KIND, "SomeUnrelatedKind"],
        expected={PROFILE_NODE_KIND, "SomeUnrelatedKind"},
    ),
    ExpandCase(
        name="empty_input_stays_empty",
        modified_kinds=[],
        expected=set(),
    ),
]


@pytest.mark.parametrize("case", EXPAND_CASES, ids=lambda case: case.name)
@pytest.mark.usefixtures("profile_schema_registered")
def test_schema_profile_expander(case: ExpandCase) -> None:
    result = SchemaProfileExpander().expand(modified_kinds=case.modified_kinds, branch=BRANCH)

    assert set(result) == case.expected
