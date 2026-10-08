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
from infrahub.core.schema import AttributeSchema, SchemaRoot
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.graphql.manager import registry as graphql_registry
from infrahub.pools.number_pool_repository import NumberPoolRepository
from infrahub.pools.schema_number_pool_synchronizer import SchemaNumberPoolSynchronizer
from infrahub.pools.schema_number_pool_upserter import SchemaNumberPoolUpserter
from tests.helpers.number_pool import (
    SCOPED_DEVICE,
    SCOPED_DEVICE_ATTRIBUTE,
    SCOPED_DEVICE_KIND,
    SCOPED_POOL_SCHEMA,
    SCOPED_SITE,
    SCOPED_TAG,
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


UNIQUE_ATTRIBUTE = "asset_number"
DEFAULT_BRANCH_KEY = "default"
FORKED_BEFORE_POD = "forked-before-pod"
POD_BRANCH = "pod-branch"
SCOPE_ERROR_SUFFIX = "at allocation_scope"
NOT_A_LIST_REFUSED = "the scope must be a list of field names"
SCHEMA_POOL_SCOPE_REFUSED = (
    "allocation_scope can't be updated on schema defined pools, update the schema in the default branch instead"
)
SCOPE_UPDATE_REFUSED = "The field 'allocation_scope' can't be changed."


def device_pool_input(
    name: str, scope: dict[str, Any] | None = None, attribute: str = SCOPED_DEVICE_ATTRIBUTE
) -> dict[str, Any]:
    data = {
        "name": {"value": name},
        "node": {"value": SCOPED_DEVICE_KIND},
        "node_attribute": {"value": attribute},
    } | bounds_input(start=1, end=100)
    if scope is not None:
        data["allocation_scope"] = scope
    return data


async def create_device_pool(
    db: InfrahubDatabase, branch: Branch, name: str, scope: dict[str, Any] | None = None
) -> dict[str, Any]:
    result = await execute(
        db=db, branch=branch, source=CREATE_SCOPED_POOL, variables={"data": device_pool_input(name=name, scope=scope)}
    )
    assert not result.errors
    assert result.data
    return result.data["CoreNumberPoolCreate"]["object"]


def error_messages(result: ExecutionResult) -> list[str]:
    return [error.message for error in result.errors or []]


def assert_scope_refused(result: ExecutionResult, expected_messages: list[str]) -> None:
    messages = error_messages(result)
    assert len(messages) == 1, messages
    assert messages[0].endswith(SCOPE_ERROR_SUFFIX)
    for expected_message in expected_messages:
        assert expected_message in messages[0]


async def save_scope(
    db: InfrahubDatabase, branch: Branch, pool_id: str, scope: list[str] | None, source: str = UPDATE_SCOPED_POOL
) -> ExecutionResult:
    return await execute(
        db=db, branch=branch, source=source, variables={"data": {"id": pool_id, "allocation_scope": {"value": scope}}}
    )


def device_schema_with_pod() -> SchemaRoot:
    device = copy.deepcopy(SCOPED_DEVICE)
    device.attributes.append(AttributeSchema(name="pod", kind="Text", optional=False))
    return SchemaRoot(nodes=[copy.deepcopy(SCOPED_SITE), copy.deepcopy(SCOPED_TAG), device])


async def read_scope(db: InfrahubDatabase, branch: Branch, pool_id: str) -> list[str] | None:
    result = await execute(db=db, branch=branch, source=QUERY_POOL_SCOPE, variables={"id": pool_id})
    assert not result.errors
    assert result.data
    return result.data["CoreNumberPool"]["edges"][0]["node"]["allocation_scope"]["value"]


class TestNumberPoolAllocationScope:
    """The allocation scope is stored on the pool and read back as written.

    The schema is loaded once for the class; every test creates pools under names of its own.
    """

    @pytest.fixture(scope="class")
    async def device_schema(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> None:
        await load_schema(db=db, schema=SCOPED_POOL_SCHEMA)
        default_branch_scope_class.update_schema_hash()

    async def test_create_with_scope_reads_it_back(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, device_schema: None
    ) -> None:
        pool = await create_device_pool(
            db=db, branch=default_branch_scope_class, name="scoped-pool", scope={"value": ["site"]}
        )

        assert pool["allocation_scope"]["value"] == ["site"]
        assert await read_scope(db=db, branch=default_branch_scope_class, pool_id=pool["id"]) == ["site"]

    async def test_create_without_scope_reads_null(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, device_schema: None
    ) -> None:
        pool = await create_device_pool(db=db, branch=default_branch_scope_class, name="unscoped-pool")

        assert await read_scope(db=db, branch=default_branch_scope_class, pool_id=pool["id"]) is None

    async def test_update_with_null_is_refused_and_keeps_the_scope(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, device_schema: None
    ) -> None:
        pool = await create_device_pool(
            db=db, branch=default_branch_scope_class, name="cleared-pool", scope={"value": ["site"]}
        )

        result = await save_scope(db=db, branch=default_branch_scope_class, pool_id=pool["id"], scope=None)

        assert error_messages(result) == [SCOPE_UPDATE_REFUSED]
        assert await read_scope(db=db, branch=default_branch_scope_class, pool_id=pool["id"]) == ["site"]


def _validation_schema() -> SchemaRoot:
    device = copy.deepcopy(SCOPED_DEVICE)
    device.attributes.extend(
        [
            AttributeSchema(name="labels", kind="List", optional=False),
            AttributeSchema(name="settings", kind="JSON", optional=False),
            AttributeSchema(name=UNIQUE_ATTRIBUTE, kind="Number", optional=True, unique=True),
        ]
    )
    return SchemaRoot(nodes=[copy.deepcopy(SCOPED_SITE), copy.deepcopy(SCOPED_TAG), device])


@dataclass
class ScopeRefusalTestCase:
    name: str
    scope: list[str]
    expected_messages: list[str]
    """Substrings the refusal carries, the first naming the entry."""


SCOPE_REFUSAL_TEST_CASES: list[ScopeRefusalTestCase] = [
    ScopeRefusalTestCase(
        name="optional-attribute",
        scope=["description"],
        expected_messages=["'description'", f"must be required on {SCOPED_DEVICE_KIND}"],
    ),
    ScopeRefusalTestCase(
        name="optional-relationship",
        scope=["parent"],
        expected_messages=["'parent'", f"must be required on {SCOPED_DEVICE_KIND}"],
    ),
    ScopeRefusalTestCase(
        name="many-relationship", scope=["tags"], expected_messages=["'tags'", "must be of cardinality one"]
    ),
    ScopeRefusalTestCase(
        name="related-node-attribute",
        scope=["site__name__value"],
        expected_messages=["'site__name__value'", "cannot use attributes of related node"],
    ),
    ScopeRefusalTestCase(
        name="related-node-attribute-without-property",
        scope=["site__name"],
        expected_messages=["'site__name'", "cannot use attributes of related node"],
    ),
    ScopeRefusalTestCase(
        name="list-attribute", scope=["labels"], expected_messages=["'labels'", "must be a single scalar value"]
    ),
    ScopeRefusalTestCase(
        name="json-attribute", scope=["settings"], expected_messages=["'settings'", "must be a single scalar value"]
    ),
    ScopeRefusalTestCase(
        name="pooled-attribute",
        scope=[SCOPED_DEVICE_ATTRIBUTE],
        expected_messages=[f"'{SCOPED_DEVICE_ATTRIBUTE}'", "cannot scope a pool by the attribute it allocates"],
    ),
    ScopeRefusalTestCase(name="duplicate", scope=["site", "site"], expected_messages=["'site'", "is a duplicate"]),
    ScopeRefusalTestCase(
        name="duplicate-after-normalisation",
        scope=["role", "role__value"],
        expected_messages=["'role__value'", "is a duplicate"],
    ),
    ScopeRefusalTestCase(
        name="undefined-on-kind",
        scope=["rack"],
        expected_messages=["'rack'", f"is not defined on {SCOPED_DEVICE_KIND}"],
    ),
]


class TestNumberPoolScopeValidation:
    """A scope that cannot divide the pool is refused at create, naming what is wrong.

    The schema is loaded once for the class; every test creates pools under names of its own.
    """

    @pytest.fixture(scope="class")
    async def device_schema(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> None:
        await load_schema(db=db, schema=_validation_schema())
        default_branch_scope_class.update_schema_hash()

    @pytest.mark.parametrize("test_case", SCOPE_REFUSAL_TEST_CASES, ids=lambda test_case: test_case.name)
    async def test_create_refuses_the_entry(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        device_schema: None,
        test_case: ScopeRefusalTestCase,
    ) -> None:
        result = await execute(
            db=db,
            branch=default_branch_scope_class,
            source=CREATE_SCOPED_POOL,
            variables={"data": device_pool_input(name=f"create-{test_case.name}", scope={"value": test_case.scope})},
        )

        assert_scope_refused(result=result, expected_messages=test_case.expected_messages)

    @pytest.mark.parametrize("value", [[1], "site"], ids=["list-of-int", "string"])
    async def test_create_refuses_a_scope_that_is_not_a_list_of_strings(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, device_schema: None, value: object
    ) -> None:
        result = await execute(
            db=db,
            branch=default_branch_scope_class,
            source=CREATE_SCOPED_POOL,
            variables={"data": device_pool_input(name=f"create-not-a-list-{value!s}", scope={"value": value})},
        )

        assert_scope_refused(result=result, expected_messages=[NOT_A_LIST_REFUSED])

    @pytest.mark.parametrize("value", [[1], "site"], ids=["list-of-int", "string"])
    async def test_update_refuses_a_scope_that_is_not_a_list_of_strings_and_keeps_the_stored_scope(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, device_schema: None, value: object
    ) -> None:
        pool = await create_device_pool(
            db=db, branch=default_branch_scope_class, name=f"update-not-a-list-{value!s}", scope={"value": ["site"]}
        )

        result = await execute(
            db=db,
            branch=default_branch_scope_class,
            source=UPDATE_SCOPED_POOL,
            variables={"data": {"id": pool["id"], "allocation_scope": {"value": value}}},
        )

        assert_scope_refused(result=result, expected_messages=[NOT_A_LIST_REFUSED])
        assert await read_scope(db=db, branch=default_branch_scope_class, pool_id=pool["id"]) == ["site"]

    async def test_upsert_creating_a_pool_refuses_the_entry(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, device_schema: None
    ) -> None:
        result = await execute(
            db=db,
            branch=default_branch_scope_class,
            source=UPSERT_SCOPED_POOL,
            variables={"data": device_pool_input(name="upsert-refused", scope={"value": ["description"]})},
        )

        assert_scope_refused(
            result=result, expected_messages=["'description'", f"must be required on {SCOPED_DEVICE_KIND}"]
        )

    async def test_create_stores_the_scope_as_bare_field_names(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, device_schema: None
    ) -> None:
        pool = await create_device_pool(
            db=db, branch=default_branch_scope_class, name="create-valid", scope={"value": ["site", "role__value"]}
        )

        assert pool["allocation_scope"]["value"] == ["site", "role"]
        assert await read_scope(db=db, branch=default_branch_scope_class, pool_id=pool["id"]) == ["site", "role"]

    async def test_upsert_creates_a_pool_with_the_scope_as_bare_field_names(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, device_schema: None
    ) -> None:
        result = await execute(
            db=db,
            branch=default_branch_scope_class,
            source=UPSERT_SCOPED_POOL,
            variables={"data": device_pool_input(name="upsert-new", scope={"value": ["site", "role__value"]})},
        )

        assert not result.errors
        assert result.data
        pool = result.data["CoreNumberPoolUpsert"]["object"]
        assert await read_scope(db=db, branch=default_branch_scope_class, pool_id=pool["id"]) == ["site", "role"]

    async def test_any_scope_on_a_unique_attribute_is_refused_naming_the_attribute(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, device_schema: None
    ) -> None:
        result = await execute(
            db=db,
            branch=default_branch_scope_class,
            source=CREATE_SCOPED_POOL,
            variables={
                "data": device_pool_input(name="unique-target", scope={"value": ["site"]}, attribute=UNIQUE_ATTRIBUTE)
            },
        )

        assert_scope_refused(result=result, expected_messages=[f"'{UNIQUE_ATTRIBUTE}'", "is unique"])


class TestNumberPoolScopeUpdate:
    """The scope is set at create; an update or upsert of the pool accepts only the stored scope, re-sent.

    The schema is loaded once for the class; every test creates pools under names of its own.
    """

    @pytest.fixture(scope="class")
    async def device_schema(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> None:
        await load_schema(db=db, schema=SCOPED_POOL_SCHEMA)
        default_branch_scope_class.update_schema_hash()

    @pytest.mark.parametrize("operation", ["update", "upsert"])
    async def test_different_scope_is_refused_and_keeps_the_stored_scope(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, device_schema: None, operation: str
    ) -> None:
        pool = await create_device_pool(
            db=db,
            branch=default_branch_scope_class,
            name=f"changed-{operation}",
            scope={"value": ["site"]},
        )

        result = await save_scope(
            db=db,
            branch=default_branch_scope_class,
            pool_id=pool["id"],
            scope=["site", "role"],
            source=SAVE_SCOPE_SOURCES[operation],
        )

        assert error_messages(result) == [SCOPE_UPDATE_REFUSED]
        assert await read_scope(db=db, branch=default_branch_scope_class, pool_id=pool["id"]) == ["site"]

    async def test_scope_on_an_unscoped_pool_is_refused_and_keeps_the_pool_unscoped(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, device_schema: None
    ) -> None:
        pool = await create_device_pool(db=db, branch=default_branch_scope_class, name="unscoped-update")

        result = await save_scope(db=db, branch=default_branch_scope_class, pool_id=pool["id"], scope=["site"])

        assert error_messages(result) == [SCOPE_UPDATE_REFUSED]
        assert await read_scope(db=db, branch=default_branch_scope_class, pool_id=pool["id"]) is None

    @pytest.mark.parametrize(
        "scope", [["site", "role"], ["site", "role__value"]], ids=["bare-field-names", "value-property"]
    )
    @pytest.mark.parametrize("operation", ["update", "upsert"])
    async def test_stored_scope_resent_is_accepted(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        device_schema: None,
        operation: str,
        scope: list[str],
    ) -> None:
        pool = await create_device_pool(
            db=db,
            branch=default_branch_scope_class,
            name=f"resent-{operation}-{scope[-1]}",
            scope={"value": ["site", "role"]},
        )

        result = await save_scope(
            db=db,
            branch=default_branch_scope_class,
            pool_id=pool["id"],
            scope=scope,
            source=SAVE_SCOPE_SOURCES[operation],
        )

        assert not result.errors
        assert await read_scope(db=db, branch=default_branch_scope_class, pool_id=pool["id"]) == ["site", "role"]


class TestNumberPoolScopeOnBranchOnlyField:
    """A field that exists only on a branch cannot enter a scope, whatever branch the pool is saved on.

    `pod` is declared on the device kind on branch `pod-branch` only.
    """

    @pytest.fixture(scope="class")
    async def pod_branch(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> Branch:
        await load_schema(db=db, schema=SCOPED_POOL_SCHEMA)
        default_branch_scope_class.update_schema_hash()
        branch = await create_branch(branch_name="pod-branch", db=db)
        await load_schema(db=db, schema=device_schema_with_pod(), branch_name=branch.name)
        return branch

    async def test_create_on_the_branch_is_refused_naming_the_entry(
        self, db: InfrahubDatabase, pod_branch: Branch
    ) -> None:
        result = await execute(
            db=db,
            branch=pod_branch,
            source=CREATE_SCOPED_POOL,
            variables={"data": device_pool_input(name="branch-create", scope={"value": ["site", "pod"]})},
        )

        assert_scope_refused(result=result, expected_messages=["'pod'", f"is not defined on {SCOPED_DEVICE_KIND}"])

    async def test_create_on_the_default_branch_is_refused_naming_the_entry(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, pod_branch: Branch
    ) -> None:
        result = await execute(
            db=db,
            branch=default_branch_scope_class,
            source=CREATE_SCOPED_POOL,
            variables={"data": device_pool_input(name="main-create", scope={"value": ["site", "pod"]})},
        )

        assert_scope_refused(result=result, expected_messages=["'pod'", f"is not defined on {SCOPED_DEVICE_KIND}"])


class TestNumberPoolScopeAfterFieldReachesDefaultBranch:
    """Once a field is in the default branch's schema, a scope naming it saves from every branch.

    `forked-before-pod` is forked before `pod` reaches the default branch, so its schema never has `pod`. The field
    reaches the default branch by loading the schema `pod-branch` carries there, which leaves the default branch's
    schema as a merge of `pod-branch` would.
    """

    @pytest.fixture(scope="class")
    async def branches(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        register_core_models_schema_scope_class: SchemaBranch,
    ) -> dict[str, Branch]:
        await load_schema(db=db, schema=SCOPED_POOL_SCHEMA)
        default_branch_scope_class.update_schema_hash()
        forked_before_pod = await create_branch(branch_name=FORKED_BEFORE_POD, db=db)
        pod_branch = await create_branch(branch_name=POD_BRANCH, db=db)
        await load_schema(db=db, schema=device_schema_with_pod(), branch_name=pod_branch.name)
        await load_schema(db=db, schema=device_schema_with_pod(), branch_name=default_branch_scope_class.name)
        return {
            DEFAULT_BRANCH_KEY: default_branch_scope_class,
            forked_before_pod.name: forked_before_pod,
            pod_branch.name: pod_branch,
        }

    @pytest.mark.parametrize("branch_name", [DEFAULT_BRANCH_KEY, FORKED_BEFORE_POD, POD_BRANCH])
    async def test_scope_saves_from_any_branch(
        self, db: InfrahubDatabase, branches: dict[str, Branch], branch_name: str
    ) -> None:
        branch = branches[branch_name]

        pool = await create_device_pool(
            db=db, branch=branch, name=f"merged-{branch_name}", scope={"value": ["site", "pod"]}
        )

        assert pool["allocation_scope"]["value"] == ["site", "pod"]

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
        assert await read_scope(db=db, branch=branches[FORKED_BEFORE_POD], pool_id=pool["id"]) == ["site", "pod"]


class TestSchemaNumberPoolScope:
    """The scope of a pool the schema created is set by the schema, not by a pool mutation."""

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

        assert error_messages(result) == [SCHEMA_POOL_SCOPE_REFUSED]
        pool = await load_pool(db=db, pool_id=schema_pool_id)
        assert not pool.get_attribute("allocation_scope").value

    @pytest.mark.parametrize("source", [UPDATE_SCOPED_POOL, UPSERT_SCOPED_POOL], ids=["update", "upsert"])
    async def test_null_scope_is_accepted_when_the_pool_stores_none(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, schema_pool_id: str, source: str
    ) -> None:
        result = await save_scope(
            db=db, branch=default_branch_scope_class, pool_id=schema_pool_id, scope=None, source=source
        )

        assert not result.errors
        pool = await load_pool(db=db, pool_id=schema_pool_id)
        assert not pool.get_attribute("allocation_scope").value
