"""A load that raises several constraints reaching the same declaration reports its schema pool once."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import SchemaPathType
from tests.unit.core.validators.number_pool_scope.declared_scope.helpers import (
    DEVICE_SCHEMA_POOL_ID,
    HOLDER_SCHEMA_POOL_ID,
    SCHEMA_POOLS,
    SCOPE_CONSTRAINT,
    declared_checker,
    declared_request,
    declared_schema,
    device_site_renamed_and_declared,
    device_vlan_id_renamed_and_declared,
    holder_declaration_cleared,
    unvalidated_schema_branch,
)
from tests.unit.core.validators.number_pool_scope.helpers import DEVICE, HOLDER, POD_HOLDER, RecordingPoolSource

if TYPE_CHECKING:
    from collections.abc import Callable

    from infrahub.core.schema import SchemaRoot


@dataclass(frozen=True)
class RaisedConstraint:
    constraint_name: str
    kind: str
    field_name: str
    path_type: SchemaPathType


@dataclass(frozen=True)
class LoadCase:
    name: str
    change: Callable[[SchemaRoot], None]
    constraints: list[RaisedConstraint]
    expected: list[tuple[str, str]]


LOAD_CASES = [
    LoadCase(
        name="generic-declaration-cleared",
        change=holder_declaration_cleared,
        constraints=[
            RaisedConstraint(
                constraint_name=SCOPE_CONSTRAINT, kind=HOLDER, field_name="vlan_id", path_type=SchemaPathType.ATTRIBUTE
            ),
            RaisedConstraint(
                constraint_name=SCOPE_CONSTRAINT,
                kind=POD_HOLDER,
                field_name="vlan_id",
                path_type=SchemaPathType.ATTRIBUTE,
            ),
        ],
        expected=[
            (HOLDER_SCHEMA_POOL_ID, "ScopeHolder.vlan_id: allocation_scope can't be changed after the pool is created")
        ],
    ),
    LoadCase(
        name="relationship-renamed-with-the-declaration-following",
        change=device_site_renamed_and_declared,
        constraints=[
            RaisedConstraint(
                constraint_name="relationship.name.update",
                kind=DEVICE,
                field_name="location",
                path_type=SchemaPathType.RELATIONSHIP,
            ),
            RaisedConstraint(
                constraint_name=SCOPE_CONSTRAINT, kind=DEVICE, field_name="vlan_id", path_type=SchemaPathType.ATTRIBUTE
            ),
        ],
        expected=[],
    ),
    LoadCase(
        name="pooled-attribute-renamed-with-its-declaration-changed",
        change=device_vlan_id_renamed_and_declared,
        constraints=[
            RaisedConstraint(
                constraint_name="attribute.name.update",
                kind=DEVICE,
                field_name="vlan_number",
                path_type=SchemaPathType.ATTRIBUTE,
            ),
            RaisedConstraint(
                constraint_name=SCOPE_CONSTRAINT,
                kind=DEVICE,
                field_name="vlan_number",
                path_type=SchemaPathType.ATTRIBUTE,
            ),
        ],
        expected=[
            (
                DEVICE_SCHEMA_POOL_ID,
                "ScopeDevice.vlan_number: allocation_scope can't be changed after the pool is created",
            )
        ],
    ),
]


@pytest.mark.parametrize("case", LOAD_CASES, ids=[case.name for case in LOAD_CASES])
async def test_reports_each_pool_once_across_the_constraints_of_one_load(case: LoadCase) -> None:
    candidate_schema = declared_schema()
    case.change(candidate_schema)
    candidate = unvalidated_schema_branch(candidate_schema)
    checker = declared_checker(pool_source=RecordingPoolSource(pools=SCHEMA_POOLS))

    refusals = [
        (path.node_id, path.value)
        for constraint in case.constraints
        for grouped in await checker.check(
            declared_request(
                candidate=candidate,
                constraint_name=constraint.constraint_name,
                kind=constraint.kind,
                field_name=constraint.field_name,
                path_type=constraint.path_type,
            )
        )
        for path in grouped.get_all_data_paths()
    ]

    assert refusals == case.expected
