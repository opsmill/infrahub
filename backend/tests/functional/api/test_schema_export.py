from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.query import QueryType
from infrahub.core.schema import SchemaRoot, core_models, internal_schema
from infrahub.core.schema.definitions.deprecated import deprecated_models
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.graphql.registry import registry as graphql_registry
from tests.helpers.schema import load_schema
from tests.helpers.schema.export_variations import (
    DERIVED_FROM_UNIQUE_ATTRIBUTE,
    RESTRICTED_NAMESPACE_EXTENSION,
    merge_variation_schemas,
)
from tests.helpers.schema_cache import install_processed_core_schema_branch
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from tests.helpers.test_client import InfrahubTestClient

DELETE_VERTICES_WITH_THEIR_FIELDS_QUERY = """
MATCH (n:Node)
WHERE n.uuid IN $ids OR n.kind IN $kinds
OPTIONAL MATCH (n)-[:HAS_ATTRIBUTE]->(attribute:Attribute)
OPTIONAL MATCH (n)-[:IS_RELATED]-(relationship:Relationship)
WITH collect(DISTINCT n) + collect(DISTINCT attribute) + collect(DISTINCT relationship) AS vertices
UNWIND vertices AS vertex
DETACH DELETE vertex
"""

COUNT_OBJECTS_OF_KINDS_QUERY = """
MATCH (n:Node)
WHERE n.kind IN $kinds
RETURN count(n) AS objects
"""


def _user_schema_ids(current: SchemaBranch, core: SchemaBranch) -> list[str]:
    """Return the IDs of the stored schema elements the schema owner added, on user kinds and on core kinds."""
    ids: list[str | None] = []
    for kind in current.node_names + current.generic_names:
        element = current.get(name=kind, duplicate=False)
        if core.has(name=kind):
            core_element = core.get(name=kind, duplicate=False)
            ids.extend(
                attribute.id for attribute in element.attributes if attribute.name not in core_element.attribute_names
            )
            ids.extend(
                relationship.id
                for relationship in element.relationships
                if relationship.name not in core_element.relationship_names
            )
            continue
        ids.append(element.id)
        ids.extend(attribute.id for attribute in element.attributes)
        ids.extend(relationship.id for relationship in element.relationships)
    return sorted({schema_id for schema_id in ids if schema_id})


async def reset_to_core_schema(db: InfrahubDatabase, branch: Branch) -> None:
    """Return the branch to the schema of an empty instance, keeping the objects of the core kinds.

    The stored user-defined schema and the objects of the user-defined kinds are deleted from the database; the
    root, the branches, the core schema and the accounts, tokens, groups and permissions stay, so API clients stay
    logged in.
    """
    current = registry.schema.get_schema_branch(name=branch.name)
    # An empty schema branch lets the cached core schema replace the user-defined one.
    registry.schema.set_schema_branch(name=branch.name, schema=SchemaBranch(cache={}, name=branch.name))
    core = install_processed_core_schema_branch(branch_name=branch.name)

    user_kinds = sorted(set(current.all_names) - set(core.all_names))
    await db.execute_query(
        query=DELETE_VERTICES_WITH_THEIR_FIELDS_QUERY,
        params={"ids": _user_schema_ids(current=current, core=core), "kinds": user_kinds},
        name="reset_to_core_schema",
        type=QueryType.WRITE,
    )

    reloaded = await registry.schema.load_schema_from_db(db=db, branch=branch, schema=core)
    registry.schema.set_schema_branch(name=branch.name, schema=reloaded)
    branch.update_schema_hash()
    await branch.save(db=db)
    graphql_registry.clear_cache()


def core_schema_kinds() -> set[str]:
    """Return the kinds of the nodes and generics that the core schema definitions define."""
    return {
        f"{element['namespace']}{element['name']}"
        for definitions in (internal_schema, core_models, deprecated_models)
        for element_type in ("nodes", "generics")
        for element in definitions.get(element_type, [])
    }


async def fetch_schema(test_client: InfrahubTestClient, token: str, branch: str) -> dict[str, Any]:
    response = await test_client.get(f"/api/schema?branch={branch}", headers={"X-INFRAHUB-KEY": token})
    assert response.status_code == 200, response.text
    return response.json()


def schema_kinds(schema: dict[str, Any]) -> set[str]:
    return {element["namespace"] + element["name"] for element in schema["nodes"] + schema["generics"]}


async def assert_holds_only_the_core_schema(test_client: InfrahubTestClient, token: str, branch: str) -> None:
    kinds = schema_kinds(await fetch_schema(test_client=test_client, token=token, branch=branch))

    assert InfrahubKind.IPNAMESPACE in kinds
    assert sorted(kinds - core_schema_kinds()) == []


def _tag_field_names(schema: dict[str, Any]) -> set[str]:
    tag = next(node for node in schema["nodes"] if node["namespace"] + node["name"] == InfrahubKind.TAG)
    return {field["name"] for field in tag["attributes"] + tag["relationships"]}


async def store_core_schema_of(db: InfrahubDatabase, kinds: list[str]) -> None:
    """Store the core schema of the given kinds in the database, as an instance does for every core kind.

    The test app keeps the core schema in memory only, and a schema extension can only reach a stored kind.
    """
    await load_schema(db=db, schema=SchemaRoot(), update_db=True, limit=kinds)


class TestResetToCoreSchema(TestInfrahubApp):
    @pytest.fixture(scope="class")
    def user_schema(self) -> dict[str, Any]:
        return merge_variation_schemas([DERIVED_FROM_UNIQUE_ATTRIBUTE, RESTRICTED_NAMESPACE_EXTENSION])

    @pytest.fixture(scope="class")
    async def stored_tag_schema(self, db: InfrahubDatabase, initialize_registry: None) -> None:
        await store_core_schema_of(db=db, kinds=[InfrahubKind.TAG])

    async def test_reset_removes_the_user_schema_and_its_objects(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        stored_tag_schema: None,
        client: InfrahubClient,
        test_client: InfrahubTestClient,
        api_admin_token: str,
        user_schema: dict[str, Any],
    ) -> None:
        schema_before_load = await fetch_schema(
            test_client=test_client, token=api_admin_token, branch=default_branch.name
        )
        core_kinds_before_load = schema_kinds(schema_before_load)
        load = await client.schema.load(schemas=[user_schema], wait_until_converged=True)
        assert load.errors == {}
        device = await client.create(kind="DerivedDevice", data={"name": "edge01"})
        await device.save()
        owner = await client.create(kind="TaggedOwner", data={"name": "network-team"})
        await owner.save()
        tag = await client.create(kind=InfrahubKind.TAG, data={"name": "blue", "owner": owner})
        await tag.save()
        loaded_schema = await fetch_schema(test_client=test_client, token=api_admin_token, branch=default_branch.name)
        assert schema_kinds(loaded_schema) - core_kinds_before_load == {"DerivedDevice", "TaggedOwner"}
        assert _tag_field_names(loaded_schema) - _tag_field_names(schema_before_load) == {"external_code", "owner"}

        await reset_to_core_schema(db=db, branch=default_branch)

        schema = await fetch_schema(test_client=test_client, token=api_admin_token, branch=default_branch.name)
        assert schema_kinds(schema) == core_kinds_before_load
        await assert_holds_only_the_core_schema(
            test_client=test_client, token=api_admin_token, branch=default_branch.name
        )
        assert _tag_field_names(schema) == _tag_field_names(schema_before_load)
        objects = await db.execute_query(
            query=COUNT_OBJECTS_OF_KINDS_QUERY, params={"kinds": ["DerivedDevice", "TaggedOwner"]}
        )
        assert objects[0]["objects"] == 0

        await client.schema.all(refresh=True)
        tags = await client.all(kind=InfrahubKind.TAG)
        assert [found.id for found in tags] == [tag.id]

    async def test_user_schema_loads_again_after_a_reset(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
        test_client: InfrahubTestClient,
        api_admin_token: str,
        user_schema: dict[str, Any],
    ) -> None:
        load = await client.schema.load(schemas=[user_schema], wait_until_converged=True)
        assert load.errors == {}
        devices = await client.all(kind="DerivedDevice")
        assert devices == []

        await reset_to_core_schema(db=db, branch=default_branch)

        await assert_holds_only_the_core_schema(
            test_client=test_client, token=api_admin_token, branch=default_branch.name
        )
