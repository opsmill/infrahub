from dataclasses import dataclass

import pytest

from infrahub.core.schema.definitions.core.group import (
    core_generator_aware_group,
    core_generator_group,
    core_graphql_query_group,
    core_repository_group,
)
from infrahub.core.schema.node_schema import NodeSchema


@dataclass
class InternalGroupKindCase:
    name: str
    """Descriptive name for the test scenario."""

    schema: NodeSchema
    """The CoreGroup subkind whose instances should default to group_type='internal'."""


INTERNAL_GROUP_KIND_CASES: list[InternalGroupKindCase] = [
    InternalGroupKindCase(name="core_generator_group", schema=core_generator_group),
    InternalGroupKindCase(name="core_generator_aware_group", schema=core_generator_aware_group),
    InternalGroupKindCase(name="core_graphql_query_group", schema=core_graphql_query_group),
    InternalGroupKindCase(name="core_repository_group", schema=core_repository_group),
]


@pytest.mark.parametrize(
    "test_case",
    [pytest.param(tc, id=tc.name) for tc in INTERNAL_GROUP_KIND_CASES],
)
def test_system_only_group_kinds_default_group_type_to_internal(test_case: InternalGroupKindCase) -> None:
    """System-managed CoreGroup subkinds should locally override group_type to default 'internal'.

    Instances of these kinds are created by Infrahub itself (permissions, generators, repositories,
    GraphQL query tracking) and should never appear in user-facing 'add to group' dropdowns. The
    canonical signal for that is group_type='internal'; inheriting the generic's 'default' value
    leaks them into selectors that filter on group_type.
    """
    group_type_attr = next(
        (attr for attr in test_case.schema.attributes if attr.name == "group_type"),
        None,
    )

    assert group_type_attr is not None, (
        f"{test_case.schema.kind} must locally declare 'group_type' instead of inheriting it from Core/Group"
    )
    assert group_type_attr.default_value == "internal"
