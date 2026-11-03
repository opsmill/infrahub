"""Renames of a kind or an attribute that a number pool allocates numbers for."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import InfrahubKind, PathType, SchemaPathType
from infrahub.core.path import SchemaPath
from infrahub.core.registry import registry
from infrahub.core.schema import GenericSchema, NodeSchema, SchemaRoot
from infrahub.core.validators.model import SchemaConstraintValidatorRequest
from infrahub.core.validators.pool.rename import NumberPoolRenameChecker
from infrahub.core.validators.pool.scope_dependency import ScopeViolationBuilder
from tests.helpers.number_pool import SCOPED_DEVICE
from tests.unit.core.validators.number_pool_scope.helpers import (
    BRANCH,
    DEVICE,
    DEVICE_POOL_BY_ROLE,
    DEVICE_POOL_BY_SITE,
    HOLDER,
    HOLDER_POOL_BY_SITE,
    POD_HOLDER_POOL_BY_SITE,
    StaticSchemaSource,
    build_schema_branch,
    device_of,
    holder_of,
    saved_schema,
    scoped_pool,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from infrahub.core.path import DataPath
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.pools.scoped_number_pool_reader import ScopedNumberPool

UNSCOPED_DEVICE_POOL = scoped_pool(pool_id="vlan-unscoped", kind=DEVICE, elements=())
POOLS = (DEVICE_POOL_BY_SITE, DEVICE_POOL_BY_ROLE, UNSCOPED_DEVICE_POOL, HOLDER_POOL_BY_SITE, POD_HOLDER_POOL_BY_SITE)

KIND_REFUSAL = "a kind cannot be renamed while a number pool allocates numbers for it"
ATTRIBUTE_REFUSAL = "an attribute cannot be renamed while a number pool allocates numbers for it"


class RecordingPoolSource:
    """Serves every pool attached to the requested kinds and records each request in order."""

    def __init__(self, pools: Iterable[ScopedNumberPool]) -> None:
        self.pools = list(pools)
        self.requested_kinds: list[set[str]] = []

    async def get_attached_to_kinds(self, kinds: Iterable[str]) -> list[ScopedNumberPool]:
        requested = set(kinds)
        self.requested_kinds.append(requested)
        return [pool for pool in self.pools if pool.kind in requested]


def device_renamed(schema: SchemaRoot) -> None:
    device_of(schema).name = "Router"


def device_namespace_renamed(schema: SchemaRoot) -> None:
    device_of(schema).namespace = "Net"


def device_name_and_namespace_renamed(schema: SchemaRoot) -> None:
    device = device_of(schema)
    device.name = "Router"
    device.namespace = "Net"


def device_vlan_id_renamed(schema: SchemaRoot) -> None:
    device_of(schema).get_attribute(name="vlan_id").name = "vlan_number"


def device_role_renamed(schema: SchemaRoot) -> None:
    device_of(schema).get_attribute(name="role").name = "function"


def device_and_vlan_id_renamed(schema: SchemaRoot) -> None:
    device_vlan_id_renamed(schema)
    device_renamed(schema)


def holder_vlan_id_renamed(schema: SchemaRoot) -> None:
    holder_of(schema).get_attribute(name="vlan_id").name = "vlan_number"


def new_device_after_device_renamed(schema: SchemaRoot) -> None:
    device_renamed(schema)
    schema.nodes.append(copy.deepcopy(SCOPED_DEVICE))


@dataclass(frozen=True)
class RenameCase:
    name: str
    constraint_name: str
    kind: str
    field_name: str
    path_type: SchemaPathType
    change: Callable[[SchemaRoot], None]
    expected: list[tuple[str, str]]
    expected_kinds_read: list[set[str]]
    pools: tuple[ScopedNumberPool, ...] = field(default=POOLS)


def kind_refusal(pool: ScopedNumberPool) -> tuple[str, str]:
    return (pool.id, f"pool {pool.name} allocates numbers for {pool.kind}.vlan_id; {KIND_REFUSAL}")


def attribute_refusal(pool: ScopedNumberPool) -> tuple[str, str]:
    return (pool.id, f"pool {pool.name} allocates numbers for {pool.kind}.vlan_id; {ATTRIBUTE_REFUSAL}")


DEVICE_POOLS = (DEVICE_POOL_BY_SITE, DEVICE_POOL_BY_ROLE, UNSCOPED_DEVICE_POOL)

REFUSED_CASES = [
    RenameCase(
        name="kind-name",
        constraint_name="node.name.update",
        kind="ScopeRouter",
        field_name="name",
        path_type=SchemaPathType.NODE,
        change=device_renamed,
        expected=[kind_refusal(pool) for pool in DEVICE_POOLS],
        expected_kinds_read=[{DEVICE}],
    ),
    RenameCase(
        name="kind-namespace",
        constraint_name="node.namespace.update",
        kind="NetDevice",
        field_name="namespace",
        path_type=SchemaPathType.NODE,
        change=device_namespace_renamed,
        expected=[kind_refusal(pool) for pool in DEVICE_POOLS],
        expected_kinds_read=[{DEVICE}],
    ),
    RenameCase(
        name="kind-name-with-its-namespace",
        constraint_name="node.name.update",
        kind="NetRouter",
        field_name="name",
        path_type=SchemaPathType.NODE,
        change=device_name_and_namespace_renamed,
        expected=[kind_refusal(pool) for pool in DEVICE_POOLS],
        expected_kinds_read=[{DEVICE}],
    ),
    RenameCase(
        name="tracked-attribute",
        constraint_name="attribute.name.update",
        kind=DEVICE,
        field_name="vlan_number",
        path_type=SchemaPathType.ATTRIBUTE,
        change=device_vlan_id_renamed,
        expected=[attribute_refusal(pool) for pool in DEVICE_POOLS],
        expected_kinds_read=[{DEVICE}],
    ),
    # A pool on a kind that implements the generic allocates numbers for the attribute it inherits.
    RenameCase(
        name="tracked-attribute-of-a-generic",
        constraint_name="attribute.name.update",
        kind=HOLDER,
        field_name="vlan_number",
        path_type=SchemaPathType.ATTRIBUTE,
        change=holder_vlan_id_renamed,
        expected=[attribute_refusal(HOLDER_POOL_BY_SITE), attribute_refusal(POD_HOLDER_POOL_BY_SITE)],
        expected_kinds_read=[{HOLDER, "ScopePodHolder"}],
    ),
]

ACCEPTED_CASES = [
    RenameCase(
        name="kind-without-pool",
        constraint_name="node.name.update",
        kind="ScopeRouter",
        field_name="name",
        path_type=SchemaPathType.NODE,
        change=device_renamed,
        expected=[],
        expected_kinds_read=[{DEVICE}],
        pools=(),
    ),
    RenameCase(
        name="namespace-renamed-with-the-name",
        constraint_name="node.namespace.update",
        kind="NetRouter",
        field_name="namespace",
        path_type=SchemaPathType.NODE,
        change=device_name_and_namespace_renamed,
        expected=[],
        expected_kinds_read=[],
    ),
    RenameCase(
        name="attribute-no-pool-tracks",
        constraint_name="attribute.name.update",
        kind=DEVICE,
        field_name="function",
        path_type=SchemaPathType.ATTRIBUTE,
        change=device_role_renamed,
        expected=[],
        expected_kinds_read=[{DEVICE}],
    ),
    RenameCase(
        name="tracked-attribute-of-a-renamed-kind",
        constraint_name="attribute.name.update",
        kind="ScopeRouter",
        field_name="vlan_number",
        path_type=SchemaPathType.ATTRIBUTE,
        change=device_and_vlan_id_renamed,
        expected=[],
        expected_kinds_read=[],
    ),
    # A kind without an id was never saved, so it renames nothing, even under the name another kind had.
    RenameCase(
        name="new-kind-named-like-a-renamed-kind",
        constraint_name="node.name.update",
        kind=DEVICE,
        field_name="name",
        path_type=SchemaPathType.NODE,
        change=new_device_after_device_renamed,
        expected=[],
        expected_kinds_read=[],
    ),
]


def build_checker(pool_source: RecordingPoolSource, schema_source: StaticSchemaSource) -> NumberPoolRenameChecker:
    return NumberPoolRenameChecker(
        pool_source=pool_source, schema_source=schema_source, violation_builder=ScopeViolationBuilder()
    )


def build_request(case: RenameCase, candidate: SchemaBranch) -> SchemaConstraintValidatorRequest:
    node_schema = candidate.get(name=case.kind, duplicate=False)
    assert isinstance(node_schema, NodeSchema | GenericSchema)
    return SchemaConstraintValidatorRequest(
        branch=BRANCH,
        constraint_name=case.constraint_name,
        node_schema=node_schema,
        schema_path=SchemaPath(
            path_type=case.path_type, schema_kind=case.kind, field_name=case.field_name, property_name="name"
        ),
        schema_branch=candidate,
    )


async def check(case: RenameCase, pool_source: RecordingPoolSource) -> list[DataPath]:
    candidate_schema = saved_schema()
    case.change(candidate_schema)
    checker = build_checker(
        pool_source=pool_source, schema_source=StaticSchemaSource(schema_branch=build_schema_branch(saved_schema()))
    )

    grouped_data_paths = await checker.check(build_request(case=case, candidate=build_schema_branch(candidate_schema)))

    return [path for grouped in grouped_data_paths for path in grouped.get_all_data_paths()]


class TestNumberPoolRenameChecker:
    @pytest.mark.parametrize("case", REFUSED_CASES, ids=[case.name for case in REFUSED_CASES])
    async def test_reports_each_pool_that_allocates_numbers_for_the_renamed_kind_or_attribute(
        self, case: RenameCase
    ) -> None:
        pool_source = RecordingPoolSource(pools=case.pools)

        data_paths = await check(case=case, pool_source=pool_source)

        assert [(path.node_id, path.value) for path in data_paths] == case.expected
        assert {(path.branch, path.path_type, path.kind, path.field_name) for path in data_paths} == {
            (BRANCH.name, PathType.NODE, InfrahubKind.NUMBERPOOL, case.field_name)
        }
        assert pool_source.requested_kinds == case.expected_kinds_read

    @pytest.mark.parametrize("case", ACCEPTED_CASES, ids=[case.name for case in ACCEPTED_CASES])
    async def test_accepts_a_rename_no_pool_depends_on(self, case: RenameCase) -> None:
        pool_source = RecordingPoolSource(pools=case.pools)

        assert await check(case=case, pool_source=pool_source) == []
        assert pool_source.requested_kinds == case.expected_kinds_read

    async def test_reads_the_kind_name_of_the_destination_for_a_candidate_built_on_it(self) -> None:
        """A proposed change or a merge builds the candidate on the destination, which still has the previous name."""
        source_schema = saved_schema()
        device_renamed(source_schema)
        candidate_schema = saved_schema()
        device_renamed(candidate_schema)
        pool_source = RecordingPoolSource(pools=POOLS)
        checker = build_checker(
            pool_source=pool_source,
            schema_source=StaticSchemaSource(
                schema_branch=build_schema_branch(source_schema),
                default_branch_schema=build_schema_branch(saved_schema(), name=registry.default_branch),
            ),
        )
        case = REFUSED_CASES[0]

        grouped_data_paths = await checker.check(
            build_request(case=case, candidate=build_schema_branch(candidate_schema, name=registry.default_branch))
        )

        data_paths = [path for grouped in grouped_data_paths for path in grouped.get_all_data_paths()]
        assert [(path.node_id, path.value) for path in data_paths] == case.expected
        assert pool_source.requested_kinds == [{DEVICE}]
