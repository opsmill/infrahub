import copy
from dataclasses import dataclass
from typing import Any

import pytest
from graphql import ExecutionResult

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.node.resource_manager.number_pool import CoreNumberPool
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.graphql.manager import registry as graphql_registry
from infrahub.pools.number_pool_repository import NumberPoolRepository
from infrahub.pools.schema_number_pool_synchronizer import SchemaNumberPoolSynchronizer
from infrahub.pools.schema_number_pool_upserter import SchemaNumberPoolUpserter
from tests.helpers.number_pool import (
    SCOPED_DEVICE,
    SCOPED_HOLDER,
    SCOPED_LINK,
    SCOPED_POD_HOLDER,
    SCOPED_POOL_SCHEMA,
    SCOPED_RACK,
    SCOPED_SITE,
)
from tests.helpers.schema import SNOW_TICKET_SCHEMA, load_schema

from .helpers import bounds_input, execute, load_pool

CREATE_SCOPED_POOL = """
mutation CreateScopedPool($data: CoreNumberPoolCreateInput!) {
  CoreNumberPoolCreate(data: $data) {
    ok
    object { id allocation_scope { value } }
  }
}
"""

UPDATE_SCOPED_POOL = """
mutation UpdateScopedPool($data: CoreNumberPoolUpdateInput!) {
  CoreNumberPoolUpdate(data: $data) {
    ok
    object { id allocation_scope { value } }
  }
}
"""

UPSERT_SCOPED_POOL = """
mutation UpsertScopedPool($data: CoreNumberPoolUpsertInput!) {
  CoreNumberPoolUpsert(data: $data) {
    ok
    object { id allocation_scope { value } }
  }
}
"""

SAVE_SCOPE_SOURCES = {"update": UPDATE_SCOPED_POOL, "upsert": UPSERT_SCOPED_POOL}

QUERY_POOL_SCOPE = """
query PoolScope($id: ID!) {
  CoreNumberPool(ids: [$id]) {
    edges { node { allocation_scope { value } } }
  }
}
"""

SCOPED_DEVICE_KIND = SCOPED_DEVICE.kind
SCOPED_DEVICE_ATTRIBUTE = "vlan_id"
SCOPED_HOLDER_KIND = SCOPED_HOLDER.kind
SCOPED_POD_HOLDER_KIND = SCOPED_POD_HOLDER.kind
UNIQUE_ATTRIBUTE = "asset_number"
DEFAULT_BRANCH_KEY = "default"
FORKED_BEFORE_POD = "forked-before-pod"
POD_BRANCH = "pod-branch"
SCOPE_UPDATE_REFUSED = "allocation_scope can't be changed after the pool is created"
NOT_A_LIST_REFUSED = "the allocation scope must be a list of entries"

type StoredScope = list[dict[str, str]]


def device_pool_input(
    name: str, scope: dict[str, Any] | None = None, attribute: str = SCOPED_DEVICE_ATTRIBUTE, kind: str | None = None
) -> dict[str, Any]:
    data = {
        "name": {"value": name},
        "node": {"value": kind or SCOPED_DEVICE_KIND},
        "node_attribute": {"value": attribute},
    } | bounds_input(start=1, end=100)
    if scope is not None:
        data["allocation_scope"] = scope
    return data


async def create_device_pool(
    db: InfrahubDatabase, branch: Branch, name: str, scope: dict[str, Any] | None = None, kind: str | None = None
) -> dict[str, Any]:
    result = await execute(
        db=db,
        branch=branch,
        source=CREATE_SCOPED_POOL,
        variables={"data": device_pool_input(name=name, scope=scope, kind=kind)},
    )
    assert not result.errors, result.errors
    assert result.data
    return result.data["CoreNumberPoolCreate"]["object"]


def error_messages(result: ExecutionResult) -> list[str]:
    return [error.message for error in result.errors or []]


def create_refusal(message: str) -> str:
    return f"{message} at allocation_scope"


async def save_scope(
    db: InfrahubDatabase, branch: Branch, pool_id: str, scope: object, source: str = UPDATE_SCOPED_POOL
) -> ExecutionResult:
    return await execute(
        db=db, branch=branch, source=source, variables={"data": {"id": pool_id, "allocation_scope": {"value": scope}}}
    )


async def read_scope(db: InfrahubDatabase, branch: Branch, pool_id: str) -> StoredScope | None:
    result = await execute(db=db, branch=branch, source=QUERY_POOL_SCOPE, variables={"id": pool_id})
    assert not result.errors
    assert result.data
    return result.data["CoreNumberPool"]["edges"][0]["node"]["allocation_scope"]["value"]


async def read_stored_scope(db: InfrahubDatabase, pool_id: str) -> StoredScope | None:
    pool = await load_pool(db=db, pool_id=pool_id)
    return pool.get_attribute("allocation_scope").value


def element_id(kind: str, name: str) -> str:
    schema = registry.schema.get(name=kind, duplicate=False)
    field = schema.get_attribute_or_none(name=name) or schema.get_relationship(name=name)
    assert field.id
    return field.id


def expected_scope(kind: str, names: list[str]) -> StoredScope:
    return [{"id": element_id(kind=kind, name=name), "name": name} for name in names]


def scope_entries(kind: str, names: list[str], form: str) -> list[Any]:
    if form == "name":
        return list(names)
    if form == "id":
        return [element_id(kind=kind, name=name) for name in names]
    return [{"id": element_id(kind=kind, name=name), "name": "ignored"} for name in names]


def _peer_schemas() -> list[NodeSchema]:
    return [copy.deepcopy(SCOPED_SITE), copy.deepcopy(SCOPED_RACK), copy.deepcopy(SCOPED_LINK)]


def _default_branch_schema() -> SchemaRoot:
    """Return the scoped test schema with an optional attribute and a unique pooled attribute added to the device."""
    device = copy.deepcopy(SCOPED_DEVICE)
    device.attributes.extend(
        [
            AttributeSchema(name="description", kind="Text", optional=True),
            AttributeSchema(name=UNIQUE_ATTRIBUTE, kind="Number", optional=True, unique=True),
        ]
    )
    return SchemaRoot(
        generics=[copy.deepcopy(SCOPED_HOLDER)], nodes=[*_peer_schemas(), device, copy.deepcopy(SCOPED_POD_HOLDER)]
    )


def device_schema_with_pod() -> SchemaRoot:
    device = copy.deepcopy(SCOPED_DEVICE)
    device.attributes.append(AttributeSchema(name="pod", kind="Text", optional=False))
    return SchemaRoot(nodes=[*_peer_schemas(), device])


def device_schema_on_branch(device: NodeSchema) -> SchemaRoot:
    """Return the device kind of the default branch with `pod` added and `role` renamed `function`, keeping its ID."""
    device = device.duplicate()
    device.get_attribute(name="role").name = "function"
    device.attributes.append(AttributeSchema(name="pod", kind="Text", optional=False))
    return SchemaRoot(nodes=[device])


@dataclass
class ScopeRefusalTestCase:
    name: str
    scope: object
    message: str
    """The refusal's text before the `at allocation_scope` suffix."""
    attribute: str = SCOPED_DEVICE_ATTRIBUTE
    kind: str = SCOPED_DEVICE_KIND
    refused_on_lookup: bool = False
    """Whether the entries name no element of the kind, which an update refuses with the same message as a create."""


SCOPE_REFUSAL_TEST_CASES: list[ScopeRefusalTestCase] = [
    ScopeRefusalTestCase(
        name="optional-attribute",
        scope=["description"],
        message=f'"description" is optional; a scope element must be required on {SCOPED_DEVICE_KIND}',
    ),
    ScopeRefusalTestCase(
        name="optional-relationship",
        scope=["rack"],
        message=f'"rack" is optional; a scope element must be required on {SCOPED_DEVICE_KIND}',
    ),
    ScopeRefusalTestCase(
        name="many-relationship",
        scope=["links"],
        message='"links" has cardinality many; a scope element must be a relationship of cardinality one',
    ),
    ScopeRefusalTestCase(
        name="list-attribute",
        scope=["tags"],
        message='"tags" is of kind List; a scope element must hold a single scalar value',
    ),
    ScopeRefusalTestCase(
        name="path",
        scope=["site__name"],
        message=f'"site__name" is a path; a scope element must be an attribute or a relationship of {SCOPED_DEVICE_KIND}'
        " itself",
        refused_on_lookup=True,
    ),
    ScopeRefusalTestCase(
        name="tracked-attribute",
        scope=[SCOPED_DEVICE_ATTRIBUTE],
        message=f'"{SCOPED_DEVICE_ATTRIBUTE}" is the attribute the pool allocates; it cannot divide the pool',
    ),
    ScopeRefusalTestCase(name="duplicate", scope=["site", "site"], message='"site" appears more than once'),
    ScopeRefusalTestCase(
        name="undefined-on-kind",
        scope=["zone"],
        message=f'"zone" is not an attribute or a relationship of {SCOPED_DEVICE_KIND} on branch main',
        refused_on_lookup=True,
    ),
    ScopeRefusalTestCase(
        name="declared-on-an-implementing-node-only",
        scope=["pod"],
        message=f'"pod" is not declared on the generic {SCOPED_HOLDER_KIND}',
        kind=SCOPED_HOLDER_KIND,
        refused_on_lookup=True,
    ),
    ScopeRefusalTestCase(
        name="unique-tracked-attribute",
        scope=["site"],
        message=f"{SCOPED_DEVICE_KIND}.{UNIQUE_ATTRIBUTE} is unique;"
        " a globally unique number cannot be allocated per division",
        attribute=UNIQUE_ATTRIBUTE,
    ),
    ScopeRefusalTestCase(name="not-a-list", scope="site", message=NOT_A_LIST_REFUSED, refused_on_lookup=True),
    ScopeRefusalTestCase(name="list-of-int", scope=[1], message=NOT_A_LIST_REFUSED, refused_on_lookup=True),
]
DEVICE_POOL_REFUSAL_TEST_CASES = [
    test_case
    for test_case in SCOPE_REFUSAL_TEST_CASES
    if test_case.kind == SCOPED_DEVICE_KIND and test_case.attribute == SCOPED_DEVICE_ATTRIBUTE
]


@pytest.fixture(autouse=True)
def number_pool_node_class() -> None:
    registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool


class TestNumberPoolAllocationScope:
    """The allocation scope is resolved at create, stored and returned as `{id, name}` elements, then fixed.

    The schema is loaded once for the class; every test creates pools under names of its own.
    """

    @pytest.fixture(scope="class")
    async def device_schema(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> None:
        await load_schema(db=db, schema=_default_branch_schema(), update_db=True)
        default_branch_scope_class.update_schema_hash()

    @pytest.mark.parametrize("form", ["name", "id", "object"])
    async def test_create_stores_the_elements_in_input_order(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, device_schema: None, form: str
    ) -> None:
        entries = scope_entries(kind=SCOPED_DEVICE_KIND, names=["role", "site"], form=form)

        pool = await create_device_pool(
            db=db, branch=default_branch_scope_class, name=f"create-by-{form}", scope={"value": entries}
        )

        expected = expected_scope(kind=SCOPED_DEVICE_KIND, names=["role", "site"])
        assert pool["allocation_scope"]["value"] == expected
        assert await read_scope(db=db, branch=default_branch_scope_class, pool_id=pool["id"]) == expected
        assert await read_stored_scope(db=db, pool_id=pool["id"]) == expected

    @pytest.mark.parametrize("scope", [None, {"value": None}, {"value": []}], ids=["absent", "null", "empty-list"])
    async def test_create_without_elements_creates_an_unscoped_pool(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, device_schema: None, scope: Any
    ) -> None:
        pool = await create_device_pool(
            db=db, branch=default_branch_scope_class, name=f"unscoped-{scope!s}", scope=scope
        )

        assert await read_scope(db=db, branch=default_branch_scope_class, pool_id=pool["id"]) is None

    async def test_create_on_an_implementing_kind_stores_the_ids_of_the_generic_fields(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, device_schema: None
    ) -> None:
        pool = await create_device_pool(
            db=db,
            branch=default_branch_scope_class,
            name="inherited-scope",
            scope={"value": ["site", "name"]},
            kind=SCOPED_POD_HOLDER_KIND,
        )

        assert await read_stored_scope(db=db, pool_id=pool["id"]) == expected_scope(
            kind=SCOPED_HOLDER_KIND, names=["site", "name"]
        )

    async def test_create_on_the_generic_accepts_its_own_fields(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, device_schema: None
    ) -> None:
        pool = await create_device_pool(
            db=db,
            branch=default_branch_scope_class,
            name="generic-scope",
            scope={"value": ["site", "name"]},
            kind=SCOPED_HOLDER_KIND,
        )

        assert await read_stored_scope(db=db, pool_id=pool["id"]) == expected_scope(
            kind=SCOPED_HOLDER_KIND, names=["site", "name"]
        )

    @pytest.mark.parametrize("source", [CREATE_SCOPED_POOL, UPSERT_SCOPED_POOL], ids=["create", "upsert"])
    @pytest.mark.parametrize("test_case", SCOPE_REFUSAL_TEST_CASES, ids=lambda test_case: test_case.name)
    async def test_create_refuses_the_entry(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        device_schema: None,
        test_case: ScopeRefusalTestCase,
        source: str,
    ) -> None:
        data = device_pool_input(
            name=f"refused-{test_case.name}",
            scope={"value": test_case.scope},
            attribute=test_case.attribute,
            kind=test_case.kind,
        )

        result = await execute(db=db, branch=default_branch_scope_class, source=source, variables={"data": data})

        assert error_messages(result) == [create_refusal(test_case.message)]

    @pytest.mark.parametrize("test_case", DEVICE_POOL_REFUSAL_TEST_CASES, ids=lambda test_case: test_case.name)
    async def test_update_refuses_an_entry_create_refuses_and_keeps_the_stored_scope(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        device_schema: None,
        test_case: ScopeRefusalTestCase,
    ) -> None:
        pool = await create_device_pool(
            db=db, branch=default_branch_scope_class, name=f"update-refused-{test_case.name}", scope={"value": ["site"]}
        )

        result = await save_scope(db=db, branch=default_branch_scope_class, pool_id=pool["id"], scope=test_case.scope)

        expected = create_refusal(test_case.message) if test_case.refused_on_lookup else SCOPE_UPDATE_REFUSED
        assert error_messages(result) == [expected]
        assert await read_stored_scope(db=db, pool_id=pool["id"]) == expected_scope(
            kind=SCOPED_DEVICE_KIND, names=["site"]
        )

    @pytest.mark.parametrize("operation", ["update", "upsert"])
    @pytest.mark.parametrize(
        ("stored_names", "scope"),
        [
            (["site"], ["site", "role"]),
            (["site"], ["role"]),
            (["site", "role"], ["role", "site"]),
            (["site"], None),
            (["site"], []),
        ],
        ids=["element-added", "element-replaced", "order-changed", "null", "empty-list"],
    )
    async def test_a_different_scope_is_refused_and_keeps_the_stored_scope(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        device_schema: None,
        operation: str,
        stored_names: list[str],
        scope: list[str] | None,
    ) -> None:
        pool = await create_device_pool(
            db=db,
            branch=default_branch_scope_class,
            name=f"changed-{operation}-{scope!s}",
            scope={"value": stored_names},
        )

        result = await save_scope(
            db=db,
            branch=default_branch_scope_class,
            pool_id=pool["id"],
            scope=scope,
            source=SAVE_SCOPE_SOURCES[operation],
        )

        assert error_messages(result) == [SCOPE_UPDATE_REFUSED]
        assert await read_stored_scope(db=db, pool_id=pool["id"]) == expected_scope(
            kind=SCOPED_DEVICE_KIND, names=stored_names
        )

    @pytest.mark.parametrize("operation", ["update", "upsert"])
    async def test_a_scope_on_an_unscoped_pool_is_refused_and_keeps_the_pool_unscoped(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, device_schema: None, operation: str
    ) -> None:
        pool = await create_device_pool(db=db, branch=default_branch_scope_class, name=f"unscoped-update-{operation}")

        result = await save_scope(
            db=db,
            branch=default_branch_scope_class,
            pool_id=pool["id"],
            scope=["site"],
            source=SAVE_SCOPE_SOURCES[operation],
        )

        assert error_messages(result) == [SCOPE_UPDATE_REFUSED]
        assert await read_scope(db=db, branch=default_branch_scope_class, pool_id=pool["id"]) is None

    @pytest.mark.parametrize("operation", ["update", "upsert"])
    @pytest.mark.parametrize("form", ["name", "id", "object"])
    async def test_the_stored_scope_resent_is_accepted(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        device_schema: None,
        operation: str,
        form: str,
    ) -> None:
        pool = await create_device_pool(
            db=db,
            branch=default_branch_scope_class,
            name=f"resent-{operation}-{form}",
            scope={"value": ["site", "role"]},
        )

        result = await save_scope(
            db=db,
            branch=default_branch_scope_class,
            pool_id=pool["id"],
            scope=scope_entries(kind=SCOPED_DEVICE_KIND, names=["site", "role"], form=form),
            source=SAVE_SCOPE_SOURCES[operation],
        )

        assert not result.errors
        assert await read_stored_scope(db=db, pool_id=pool["id"]) == expected_scope(
            kind=SCOPED_DEVICE_KIND, names=["site", "role"]
        )

    async def test_upsert_with_identical_fields_is_accepted(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, device_schema: None
    ) -> None:
        pool = await create_device_pool(
            db=db, branch=default_branch_scope_class, name="upsert-identical", scope={"value": ["site", "role"]}
        )
        stored = await read_stored_scope(db=db, pool_id=pool["id"])

        result = await execute(
            db=db,
            branch=default_branch_scope_class,
            source=UPSERT_SCOPED_POOL,
            variables={
                "data": {"id": pool["id"]} | device_pool_input(name="upsert-identical", scope={"value": stored})
            },
        )

        assert not result.errors
        assert await read_stored_scope(db=db, pool_id=pool["id"]) == stored

    @pytest.mark.parametrize("operation", ["update", "upsert"])
    async def test_null_on_an_unscoped_pool_is_accepted(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, device_schema: None, operation: str
    ) -> None:
        pool = await create_device_pool(db=db, branch=default_branch_scope_class, name=f"unscoped-null-{operation}")

        result = await save_scope(
            db=db,
            branch=default_branch_scope_class,
            pool_id=pool["id"],
            scope=None,
            source=SAVE_SCOPE_SOURCES[operation],
        )

        assert not result.errors
        assert await read_scope(db=db, branch=default_branch_scope_class, pool_id=pool["id"]) is None


class TestNumberPoolScopeOnBranchSchema:
    """The scope resolves on the default branch's schema whatever branch the mutation runs on.

    On branch `pod-branch`, the device kind declares `pod` and its `role` attribute is renamed `function`, keeping
    its ID. The branch's schema is registered only, as a schema saved on the default branch carries the IDs.
    """

    @pytest.fixture(scope="class")
    async def pod_branch(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> Branch:
        await load_schema(db=db, schema=SCOPED_POOL_SCHEMA, update_db=True)
        default_branch_scope_class.update_schema_hash()
        branch = await create_branch(branch_name=POD_BRANCH, db=db)
        device = registry.schema.get_node_schema(name=SCOPED_DEVICE_KIND, branch=branch, duplicate=True)
        await load_schema(db=db, schema=device_schema_on_branch(device=device), branch_name=branch.name)
        return branch

    async def test_create_on_the_branch_with_a_field_only_the_branch_defines_is_refused(
        self, db: InfrahubDatabase, pod_branch: Branch
    ) -> None:
        result = await execute(
            db=db,
            branch=pod_branch,
            source=CREATE_SCOPED_POOL,
            variables={"data": device_pool_input(name="branch-create", scope={"value": ["site", "pod"]})},
        )

        assert error_messages(result) == [
            create_refusal(f'"pod" is not an attribute or a relationship of {SCOPED_DEVICE_KIND} on branch main')
        ]

    async def test_a_field_renamed_on_the_branch_reads_as_stored_on_each_branch(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, pod_branch: Branch
    ) -> None:
        pool = await create_device_pool(
            db=db, branch=default_branch_scope_class, name="renamed-read", scope={"value": ["site", "role"]}
        )
        stored = await read_stored_scope(db=db, pool_id=pool["id"])

        assert await read_scope(db=db, branch=default_branch_scope_class, pool_id=pool["id"]) == stored
        assert await read_scope(db=db, branch=pod_branch, pool_id=pool["id"]) == stored

    @pytest.mark.parametrize("operation", ["update", "upsert"])
    async def test_the_stored_scope_resent_on_the_branch_is_accepted(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, pod_branch: Branch, operation: str
    ) -> None:
        pool = await create_device_pool(
            db=db, branch=default_branch_scope_class, name=f"renamed-{operation}", scope={"value": ["site", "role"]}
        )
        stored = await read_stored_scope(db=db, pool_id=pool["id"])

        result = await save_scope(
            db=db, branch=pod_branch, pool_id=pool["id"], scope=stored, source=SAVE_SCOPE_SOURCES[operation]
        )

        assert not result.errors
        assert await read_stored_scope(db=db, pool_id=pool["id"]) == stored

    async def test_the_branch_name_of_a_renamed_field_is_refused(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, pod_branch: Branch
    ) -> None:
        pool = await create_device_pool(
            db=db, branch=default_branch_scope_class, name="renamed-branch-name", scope={"value": ["site", "role"]}
        )

        result = await save_scope(db=db, branch=pod_branch, pool_id=pool["id"], scope=["site", "function"])

        assert error_messages(result) == [
            create_refusal(f'"function" is not an attribute or a relationship of {SCOPED_DEVICE_KIND} on branch main')
        ]


class TestNumberPoolScopeAfterFieldReachesDefaultBranch:
    """Once a field is in the default branch's schema, a scope naming it saves from every branch.

    `forked-before-pod` is forked before `pod` reaches the default branch, so its schema never has `pod`.
    `pod-branch` is created after, so it holds `pod` under the same ID, as a merge would leave it.
    """

    @pytest.fixture(scope="class")
    async def branches(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> dict[str, Branch]:
        await load_schema(db=db, schema=SCOPED_POOL_SCHEMA, update_db=True)
        default_branch_scope_class.update_schema_hash()
        forked_before_pod = await create_branch(branch_name=FORKED_BEFORE_POD, db=db)
        await load_schema(
            db=db, schema=device_schema_with_pod(), branch_name=default_branch_scope_class.name, update_db=True
        )
        pod_branch = await create_branch(branch_name=POD_BRANCH, db=db)
        return {
            DEFAULT_BRANCH_KEY: default_branch_scope_class,
            forked_before_pod.name: forked_before_pod,
            pod_branch.name: pod_branch,
        }

    @pytest.mark.parametrize("branch_name", [DEFAULT_BRANCH_KEY, FORKED_BEFORE_POD, POD_BRANCH])
    async def test_scope_saves_from_any_branch(
        self, db: InfrahubDatabase, branches: dict[str, Branch], branch_name: str
    ) -> None:
        pool = await create_device_pool(
            db=db, branch=branches[branch_name], name=f"merged-{branch_name}", scope={"value": ["site", "pod"]}
        )

        assert await read_stored_scope(db=db, pool_id=pool["id"]) == expected_scope(
            kind=SCOPED_DEVICE_KIND, names=["site", "pod"]
        )

    async def test_pool_resent_whole_from_a_branch_forked_before_the_field_saves(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, branches: dict[str, Branch]
    ) -> None:
        pool = await create_device_pool(
            db=db, branch=default_branch_scope_class, name="resent-whole", scope={"value": ["site", "pod"]}
        )

        result = await execute(
            db=db,
            branch=branches[FORKED_BEFORE_POD],
            source=UPDATE_SCOPED_POOL,
            variables={
                "data": {"id": pool["id"]} | device_pool_input(name="resent-whole", scope={"value": ["site", "pod"]})
            },
        )

        assert not result.errors
        expected = expected_scope(kind=SCOPED_DEVICE_KIND, names=["site", "pod"])
        assert await read_scope(db=db, branch=branches[FORKED_BEFORE_POD], pool_id=pool["id"]) == expected


class TestSchemaNumberPoolScope:
    """A pool the schema created refuses a scope change through the pool mutations like a user-created pool."""

    @pytest.fixture(scope="class")
    async def schema_pool_id(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> str:
        await load_schema(db=db, schema=SNOW_TICKET_SCHEMA)
        upserter = SchemaNumberPoolUpserter(
            db=db, schema_manager=registry.schema, range_store_factory=NumberPoolRepository
        )
        synchronizer = SchemaNumberPoolSynchronizer(
            db=db, schema_manager=registry.schema, upserter=upserter, range_store_factory=NumberPoolRepository
        )
        await synchronizer.run()
        registry.node[InfrahubKind.NUMBERPOOL] = CoreNumberPool
        graphql_registry.clear_cache()
        default_branch_scope_class.update_schema_hash()

        number_attribute = registry.schema.get(name="SnowTask", branch=default_branch_scope_class).get_attribute(
            name="number"
        )
        assert isinstance(number_attribute.parameters, NumberPoolParameters)
        assert number_attribute.parameters.number_pool_id
        return number_attribute.parameters.number_pool_id

    @pytest.mark.parametrize("source", [UPDATE_SCOPED_POOL, UPSERT_SCOPED_POOL], ids=["update", "upsert"])
    async def test_scope_change_is_refused_and_leaves_the_pool_untouched(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, schema_pool_id: str, source: str
    ) -> None:
        result = await save_scope(
            db=db, branch=default_branch_scope_class, pool_id=schema_pool_id, scope=["title"], source=source
        )

        assert error_messages(result) == [SCOPE_UPDATE_REFUSED]
        assert not await read_stored_scope(db=db, pool_id=schema_pool_id)

    @pytest.mark.parametrize("source", [UPDATE_SCOPED_POOL, UPSERT_SCOPED_POOL], ids=["update", "upsert"])
    async def test_null_scope_is_accepted_when_the_pool_stores_none(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, schema_pool_id: str, source: str
    ) -> None:
        result = await save_scope(
            db=db, branch=default_branch_scope_class, pool_id=schema_pool_id, scope=None, source=source
        )

        assert not result.errors
        assert not await read_stored_scope(db=db, pool_id=schema_pool_id)


class TestNumberPoolScopeAfterTheSchemaChangesAnElement:
    """A pool sent with its stored scope still saves once the default branch's schema makes an element optional."""

    @pytest.fixture(scope="class")
    async def pool(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> dict[str, Any]:
        await load_schema(db=db, schema=SCOPED_POOL_SCHEMA, update_db=True)
        default_branch_scope_class.update_schema_hash()
        pool = await create_device_pool(
            db=db, branch=default_branch_scope_class, name="element-changed", scope={"value": ["site", "role"]}
        )
        device = copy.deepcopy(SCOPED_DEVICE)
        device.get_attribute(name="role").optional = True
        await load_schema(
            db=db,
            schema=SchemaRoot(nodes=[*_peer_schemas(), device]),
            branch_name=default_branch_scope_class.name,
            update_db=True,
        )
        default_branch_scope_class.update_schema_hash()
        assert registry.schema.get(name=SCOPED_DEVICE_KIND, duplicate=False).get_attribute(name="role").optional
        return pool

    @pytest.mark.parametrize("operation", ["update", "upsert"])
    @pytest.mark.parametrize("form", ["name", "id", "object"])
    async def test_the_stored_scope_resent_is_accepted(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        pool: dict[str, Any],
        operation: str,
        form: str,
    ) -> None:
        result = await save_scope(
            db=db,
            branch=default_branch_scope_class,
            pool_id=pool["id"],
            scope=scope_entries(kind=SCOPED_DEVICE_KIND, names=["site", "role"], form=form),
            source=SAVE_SCOPE_SOURCES[operation],
        )

        assert not result.errors
        assert await read_stored_scope(db=db, pool_id=pool["id"]) == expected_scope(
            kind=SCOPED_DEVICE_KIND, names=["site", "role"]
        )

    async def test_an_update_without_the_scope_keeps_it(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, pool: dict[str, Any]
    ) -> None:
        result = await execute(
            db=db,
            branch=default_branch_scope_class,
            source=UPDATE_SCOPED_POOL,
            variables={"data": {"id": pool["id"], "description": {"value": "renamed"}}},
        )

        assert not result.errors
        assert await read_stored_scope(db=db, pool_id=pool["id"]) == expected_scope(
            kind=SCOPED_DEVICE_KIND, names=["site", "role"]
        )
