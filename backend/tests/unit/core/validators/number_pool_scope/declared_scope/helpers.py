"""Schemas, schema pools and builders for the checks of a declared allocation scope."""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from infrahub.core.constants import SchemaPathType
from infrahub.core.path import SchemaPath
from infrahub.core.registry import registry
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.validators.model import SchemaConstraintValidatorRequest
from tests.helpers.number_pool import (
    SCOPED_DEVICE,
    SCOPED_HOLDER,
    SCOPED_LINK,
    SCOPED_POD_HOLDER,
    SCOPED_RACK,
    SCOPED_SITE,
)
from tests.unit.core.validators.number_pool_scope.helpers import (
    BRANCH,
    DEVICE,
    DEVICE_ROLE,
    DEVICE_SITE,
    HOLDER,
    HOLDER_SITE,
    POD_HOLDER,
    RecordingPoolSource,
    StaticSchemaSource,
    build_checker,
    device_of,
    device_site_renamed,
    holder_of,
    scoped_pool,
    with_field_ids,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from infrahub.core.validators.pool.scope import NumberPoolScopeChecker
    from infrahub.pools.scoped_number_pool_reader import ScopedNumberPool
DEVICE_SCHEMA_POOL_ID = "device-schema-pool"
HOLDER_SCHEMA_POOL_ID = "holder-schema-pool"
POD_HOLDER_SCHEMA_POOL_ID = "pod-holder-schema-pool"

CANNOT_CHANGE = "ScopeDevice.vlan_id: allocation_scope can't be changed after the pool is created"
SCOPE_CONSTRAINT = "attribute.parameters.allocation_scope.update"


def with_pooled_attribute[SchemaT: (NodeSchema, GenericSchema)](
    schema: SchemaT, scope: list[str], pool_id: str, name: str = "vlan_id"
) -> SchemaT:
    """Return a copy of the schema whose attribute is the NumberPool attribute of a pool the schema created."""
    pooled: SchemaT = copy.deepcopy(schema)
    pooled.attributes = [attribute for attribute in pooled.attributes if attribute.name != name]
    pooled.attributes.append(
        AttributeSchema(
            name=name,
            kind="NumberPool",
            optional=False,
            read_only=True,
            parameters=NumberPoolParameters(
                start_range=1, end_range=100, allocation_scope=scope, number_pool_id=pool_id
            ),
        )
    )
    return pooled


def declared_schema() -> SchemaRoot:
    return SchemaRoot(
        generics=[with_field_ids(with_pooled_attribute(SCOPED_HOLDER, scope=["site"], pool_id=HOLDER_SCHEMA_POOL_ID))],
        nodes=[
            SCOPED_SITE,
            SCOPED_RACK,
            SCOPED_LINK,
            with_field_ids(with_pooled_attribute(SCOPED_DEVICE, scope=["site", "role"], pool_id=DEVICE_SCHEMA_POOL_ID)),
            with_field_ids(
                with_pooled_attribute(
                    SCOPED_POD_HOLDER, scope=["site"], pool_id=POD_HOLDER_SCHEMA_POOL_ID, name="pod_number"
                )
            ),
        ],
    )


def unvalidated_schema_branch(schema: SchemaRoot, name: str = BRANCH.name) -> SchemaBranch:
    """Return the schema as a load holds it before validation, which would need a default branch's schema."""
    schema_branch = SchemaBranch(cache={}, name=name)
    schema_branch.load_schema(schema=schema)
    schema_branch.process(validate_schema=False)
    return schema_branch


def declare_on_device(scope: list[str] | None) -> Callable[[SchemaRoot], None]:
    def change(schema: SchemaRoot) -> None:
        parameters = device_of(schema).get_attribute(name="vlan_id").parameters
        assert isinstance(parameters, NumberPoolParameters)
        parameters.allocation_scope = scope

    return change


def holder_declaration_cleared(schema: SchemaRoot) -> None:
    parameters = holder_of(schema).get_attribute(name="vlan_id").parameters
    assert isinstance(parameters, NumberPoolParameters)
    parameters.allocation_scope = []


def device_site_renamed_and_declared(schema: SchemaRoot) -> None:
    device_site_renamed(schema)
    declare_on_device(["location", "role"])(schema)


def device_tags_renamed(schema: SchemaRoot) -> None:
    device_of(schema).get_attribute(name="tags").name = "labels"


def holder_site_renamed(schema: SchemaRoot) -> None:
    holder_of(schema).get_relationship(name="site").name = "location"


def device_vlan_id_renamed_and_declared(schema: SchemaRoot) -> None:
    declare_on_device(["site"])(schema)
    device_of(schema).get_attribute(name="vlan_id").name = "vlan_number"


def without_device(schema: SchemaRoot) -> None:
    schema.nodes = [node for node in schema.nodes if node.kind != DEVICE]


DEVICE_SCHEMA_POOL = scoped_pool(pool_id=DEVICE_SCHEMA_POOL_ID, kind=DEVICE, elements=(DEVICE_SITE, DEVICE_ROLE))
HOLDER_SCHEMA_POOL = scoped_pool(pool_id=HOLDER_SCHEMA_POOL_ID, kind=HOLDER, elements=(HOLDER_SITE,))
POD_HOLDER_SCHEMA_POOL = scoped_pool(pool_id=POD_HOLDER_SCHEMA_POOL_ID, kind=POD_HOLDER, elements=(HOLDER_SITE,))
UNSCOPED_DEVICE_SCHEMA_POOL = scoped_pool(pool_id=DEVICE_SCHEMA_POOL_ID, kind=DEVICE, elements=())

SCHEMA_POOLS = (DEVICE_SCHEMA_POOL, HOLDER_SCHEMA_POOL, POD_HOLDER_SCHEMA_POOL)


def declared_checker(
    pool_source: RecordingPoolSource, branch_schema: SchemaRoot | None = None, default_schema: SchemaRoot | None = None
) -> NumberPoolScopeChecker:
    return build_checker(
        pool_source=pool_source,
        schema_source=StaticSchemaSource(
            schema_branch=unvalidated_schema_branch(branch_schema or declared_schema()),
            default_branch_schema=unvalidated_schema_branch(
                default_schema or declared_schema(), name=registry.default_branch
            ),
        ),
    )


def declared_request(
    candidate: SchemaBranch, constraint_name: str, kind: str, field_name: str, path_type: SchemaPathType
) -> SchemaConstraintValidatorRequest:
    node_schema = candidate.get(name=kind, duplicate=False)
    assert isinstance(node_schema, NodeSchema | GenericSchema)
    return SchemaConstraintValidatorRequest(
        branch=BRANCH,
        constraint_name=constraint_name,
        node_schema=node_schema,
        schema_path=SchemaPath(path_type=path_type, schema_kind=kind, field_name=field_name),
        schema_branch=candidate,
    )


@dataclass(frozen=True)
class DeclarationCase:
    name: str
    constraint_name: str
    kind: str
    field_name: str
    path_type: SchemaPathType
    change: Callable[[SchemaRoot], None]
    expected: list[tuple[str, str]]
    expected_ids_read: list[set[str]]
    pools: tuple[ScopedNumberPool, ...] = field(default=SCHEMA_POOLS)


def declaration_change(name: str, scope: list[str], expected: list[tuple[str, str]]) -> DeclarationCase:
    return DeclarationCase(
        name=name,
        constraint_name=SCOPE_CONSTRAINT,
        kind=DEVICE,
        field_name="vlan_id",
        path_type=SchemaPathType.ATTRIBUTE,
        change=declare_on_device(scope),
        expected=expected,
        expected_ids_read=[{DEVICE_SCHEMA_POOL_ID}],
    )


def exact_message(message: str) -> str:
    return f"^{re.escape(message)}$"
