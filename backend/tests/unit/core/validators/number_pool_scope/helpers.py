from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from infrahub.core.branch import Branch
from infrahub.core.constants import RelationshipCardinality, SchemaPathType
from infrahub.core.path import SchemaPath
from infrahub.core.registry import registry
from infrahub.core.schema import GenericSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.validators.model import SchemaConstraintValidatorRequest
from infrahub.core.validators.pool.scope import NumberPoolScopeChecker, SchemaBranchSource, ScopedNumberPoolSource
from infrahub.core.validators.pool.scope_dependency import DependentPoolFinder, ScopeViolationBuilder
from infrahub.pools.scope import AllocationScope, ScopeElement
from infrahub.pools.scoped_number_pool_reader import ScopedNumberPool
from tests.helpers.number_pool import (
    SCOPED_DEVICE,
    SCOPED_HOLDER,
    SCOPED_LINK,
    SCOPED_POD_HOLDER,
    SCOPED_RACK,
    SCOPED_SITE,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

BRANCH = Branch(name="feature")

DEVICE = "ScopeDevice"
HOLDER = "ScopeHolder"
POD_HOLDER = "ScopePodHolder"


def field_id(kind: str, name: str) -> str:
    return f"{kind}-{name}-id"


def with_field_ids[SchemaT: (NodeSchema, GenericSchema)](schema: SchemaT) -> SchemaT:
    """Return a copy of the schema whose own fields hold the ids a saved schema gives them."""
    saved: SchemaT = copy.deepcopy(schema)
    for attribute in saved.attributes:
        attribute.id = field_id(kind=saved.kind, name=attribute.name)
    for relationship in saved.relationships:
        relationship.id = field_id(kind=saved.kind, name=relationship.name)
    return saved


def saved_schema() -> SchemaRoot:
    return SchemaRoot(
        generics=[with_field_ids(SCOPED_HOLDER)],
        nodes=[
            SCOPED_SITE,
            SCOPED_RACK,
            SCOPED_LINK,
            with_field_ids(SCOPED_DEVICE),
            with_field_ids(SCOPED_POD_HOLDER),
        ],
    )


def build_schema_branch(schema: SchemaRoot, name: str = BRANCH.name) -> SchemaBranch:
    schema_branch = SchemaBranch(cache={}, name=name)
    schema_branch.load_schema(schema=schema)
    schema_branch.process()
    return schema_branch


def device_of(schema: SchemaRoot) -> NodeSchema:
    return next(node for node in schema.nodes if node.kind == DEVICE)


def holder_of(schema: SchemaRoot) -> GenericSchema:
    return next(generic for generic in schema.generics if generic.kind == HOLDER)


def unchanged(schema: SchemaRoot) -> None:
    del schema


def device_site_optional(schema: SchemaRoot) -> None:
    device_of(schema).get_relationship(name="site").optional = True


def device_site_many(schema: SchemaRoot) -> None:
    device_of(schema).get_relationship(name="site").cardinality = RelationshipCardinality.MANY


def device_role_optional(schema: SchemaRoot) -> None:
    device_of(schema).get_attribute(name="role").optional = True


def device_vlan_id_unique(schema: SchemaRoot) -> None:
    device_of(schema).get_attribute(name="vlan_id").unique = True


def device_vlan_id_renamed_and_made_unique(schema: SchemaRoot) -> None:
    attribute = device_of(schema).get_attribute(name="vlan_id")
    attribute.name = "vlan"
    attribute.unique = True


def device_role_kind(kind: str) -> Callable[[SchemaRoot], None]:
    def change(schema: SchemaRoot) -> None:
        device_of(schema).get_attribute(name="role").kind = kind

    return change


def device_site_removed(schema: SchemaRoot) -> None:
    device = device_of(schema)
    device.relationships = [relationship for relationship in device.relationships if relationship.name != "site"]


def device_role_removed(schema: SchemaRoot) -> None:
    device = device_of(schema)
    device.attributes = [attribute for attribute in device.attributes if attribute.name != "role"]


def device_tags_removed(schema: SchemaRoot) -> None:
    device = device_of(schema)
    device.attributes = [attribute for attribute in device.attributes if attribute.name != "tags"]


def device_site_renamed(schema: SchemaRoot) -> None:
    device_of(schema).get_relationship(name="site").name = "location"


def device_role_renamed(schema: SchemaRoot) -> None:
    device_of(schema).get_attribute(name="role").name = "function"


def device_site_renamed_and_made_optional(schema: SchemaRoot) -> None:
    relationship = device_of(schema).get_relationship(name="site")
    relationship.name = "location"
    relationship.optional = True


def holder_site_optional(schema: SchemaRoot) -> None:
    holder_of(schema).get_relationship(name="site").optional = True


def pod_removed(schema: SchemaRoot) -> None:
    pod_holder = next(node for node in schema.nodes if node.kind == POD_HOLDER)
    pod_holder.attributes = [attribute for attribute in pod_holder.attributes if attribute.name != "pod"]


def scoped_pool(pool_id: str, kind: str, elements: tuple[ScopeElement, ...]) -> ScopedNumberPool:
    return ScopedNumberPool(
        id=pool_id, name=pool_id, kind=kind, tracked_attribute="vlan_id", scope=AllocationScope(elements=elements)
    )


DEVICE_SITE = ScopeElement(id=field_id(kind=DEVICE, name="site"), name="site")
DEVICE_ROLE = ScopeElement(id=field_id(kind=DEVICE, name="role"), name="role")
HOLDER_SITE = ScopeElement(id=field_id(kind=HOLDER, name="site"), name="site")

DEVICE_POOL_BY_SITE = scoped_pool(pool_id="vlan-per-site", kind=DEVICE, elements=(DEVICE_SITE,))
DEVICE_POOL_BY_ROLE = scoped_pool(pool_id="vlan-per-role", kind=DEVICE, elements=(DEVICE_ROLE,))
HOLDER_POOL_BY_SITE = scoped_pool(pool_id="holder-per-site", kind=HOLDER, elements=(HOLDER_SITE,))
POD_HOLDER_POOL_BY_SITE = scoped_pool(pool_id="pod-holder-per-site", kind=POD_HOLDER, elements=(HOLDER_SITE,))

ALL_POOLS = (DEVICE_POOL_BY_SITE, DEVICE_POOL_BY_ROLE, HOLDER_POOL_BY_SITE, POD_HOLDER_POOL_BY_SITE)


class RecordingPoolSource:
    """Serves the scoped pools of the requested kinds and records each request in order."""

    def __init__(self, pools: Iterable[ScopedNumberPool]) -> None:
        self.pools = list(pools)
        self.requested_kinds: list[set[str]] = []

    async def get_for_kinds(self, kinds: Iterable[str]) -> list[ScopedNumberPool]:
        requested = set(kinds)
        self.requested_kinds.append(requested)
        return [pool for pool in self.pools if pool.kind in requested]


class StaticSchemaSource:
    def __init__(self, schema_branch: SchemaBranch, default_branch_schema: SchemaBranch | None = None) -> None:
        self.schema_branch = schema_branch
        self.default_branch_schema = default_branch_schema

    def get_schema_branch(self, name: str) -> SchemaBranch:
        if name == registry.default_branch and self.default_branch_schema is not None:
            return self.default_branch_schema
        assert name == BRANCH.name
        return self.schema_branch

    def has_schema_branch(self, name: str) -> bool:
        return name == BRANCH.name or (name == registry.default_branch and self.default_branch_schema is not None)


@dataclass(frozen=True)
class SchemaChangeCase:
    name: str
    constraint_name: str
    kind: str
    field_name: str
    path_type: SchemaPathType
    change: Callable[[SchemaRoot], None]
    expected_kinds_read: list[set[str]]
    expected: list[tuple[str, str]] = field(default_factory=list)
    pools: tuple[ScopedNumberPool, ...] = field(default=ALL_POOLS)


def build_request(case: SchemaChangeCase, candidate: SchemaBranch) -> SchemaConstraintValidatorRequest:
    node_schema = candidate.get(name=case.kind, duplicate=False)
    assert isinstance(node_schema, NodeSchema | GenericSchema)
    return SchemaConstraintValidatorRequest(
        branch=BRANCH,
        constraint_name=case.constraint_name,
        node_schema=node_schema,
        schema_path=SchemaPath(path_type=case.path_type, schema_kind=case.kind, field_name=case.field_name),
        schema_branch=candidate,
    )


def build_checker(pool_source: ScopedNumberPoolSource, schema_source: SchemaBranchSource) -> NumberPoolScopeChecker:
    return NumberPoolScopeChecker(
        pool_source=pool_source,
        schema_source=schema_source,
        pool_finder=DependentPoolFinder(),
        violation_builder=ScopeViolationBuilder(),
    )
