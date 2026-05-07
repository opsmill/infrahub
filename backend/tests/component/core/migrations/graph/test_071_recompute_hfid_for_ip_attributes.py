from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest
import ujson

from infrahub.core import registry
from infrahub.core.constants import BranchSupportType
from infrahub.core.initialization import create_branch
from infrahub.core.migrations.graph.m071_recompute_hfid_for_ip_attributes import Migration071
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


@dataclass(frozen=True)
class NormalizedKindCase:
    kind: str
    schema_name: str
    attr_name: str
    attr_kind: str
    raw_value: str
    canonical_value: str
    node_name: str

    @property
    def display_label_template(self) -> str:
        return f"{{{{ name__value }}}} <{{{{ {self.attr_name}__value }}}}>"

    def raw_display_label(self, name: str | None = None) -> str:
        return f"{name or self.node_name} <{self.raw_value}>"

    def canonical_display_label(self, name: str | None = None) -> str:
        return f"{name or self.node_name} <{self.canonical_value}>"


CASES: list[NormalizedKindCase] = [
    NormalizedKindCase(
        kind="TestingIpDevice",
        schema_name="IpDevice",
        attr_name="primary_address",
        attr_kind="IPHost",
        raw_value="192.168.1.1",
        canonical_value="192.168.1.1/32",
        node_name="router-01",
    ),
    NormalizedKindCase(
        kind="TestingNetwork",
        schema_name="Network",
        attr_name="cidr",
        attr_kind="IPNetwork",
        raw_value="10.0.0.0/255.255.255.0",
        canonical_value="10.0.0.0/24",
        node_name="lan-a",
    ),
]


def _schema_root() -> SchemaRoot:
    return SchemaRoot(
        nodes=[
            NodeSchema(
                name=case.schema_name,
                namespace="Testing",
                branch=BranchSupportType.AWARE,
                human_friendly_id=[f"{case.attr_name}__value"],
                display_label=case.display_label_template,
                attributes=[
                    AttributeSchema(name="name", kind="Text", unique=True),
                    AttributeSchema(name=case.attr_name, kind=case.attr_kind, optional=False),
                ],
            )
            for case in CASES
        ],
    )


async def _set_attribute_value(db: InfrahubDatabase, node_uuid: str, attr_name: str, value: str) -> None:
    """Manually rewrite an attribute value in the DB, bypassing input-time normalization."""
    query = """
    MATCH (n:Node {uuid: $node_uuid})-[:HAS_ATTRIBUTE]->(a:Attribute {name: $attr_name})
    MATCH (a)-[hv:HAS_VALUE]->(av:AttributeValue)
    WHERE hv.status = "active" AND hv.to IS NULL
    SET av.value = $value
    """
    await db.execute_query(query=query, params={"node_uuid": node_uuid, "attr_name": attr_name, "value": value})


async def _set_attribute_value_on_branch(
    db: InfrahubDatabase, node_uuid: str, attr_name: str, value: str, branch_name: str
) -> None:
    """Manually rewrite the branch-specific value of an attribute, bypassing input-time normalization."""
    query = """
    MATCH (n:Node {uuid: $node_uuid})-[:HAS_ATTRIBUTE]->(a:Attribute {name: $attr_name})
    MATCH (a)-[hv:HAS_VALUE]->(av:AttributeValue)
    WHERE hv.status = "active" AND hv.to IS NULL AND hv.branch = $branch_name
    SET av.value = $value
    """
    await db.execute_query(
        query=query,
        params={"node_uuid": node_uuid, "attr_name": attr_name, "value": value, "branch_name": branch_name},
    )


async def _read_attribute_value(db: InfrahubDatabase, node_uuid: str, attr_name: str) -> str | None:
    query = """
    MATCH (n:Node {uuid: $node_uuid})-[:HAS_ATTRIBUTE]->(a:Attribute {name: $attr_name})
    MATCH (a)-[hv:HAS_VALUE]->(av:AttributeValue)
    WHERE hv.status = "active" AND hv.to IS NULL
    RETURN av.value AS value
    """
    results = await db.execute_query(query=query, params={"node_uuid": node_uuid, "attr_name": attr_name})
    if not results:
        return None
    return results[0]["value"]


async def _read_attribute_value_on_branch(
    db: InfrahubDatabase, node_uuid: str, attr_name: str, branch_name: str
) -> str | None:
    query = """
    MATCH (n:Node {uuid: $node_uuid})-[:HAS_ATTRIBUTE]->(a:Attribute {name: $attr_name})
    MATCH (a)-[hv:HAS_VALUE]->(av:AttributeValue)
    WHERE hv.status = "active" AND hv.to IS NULL AND hv.branch = $branch_name
    RETURN av.value AS value
    """
    results = await db.execute_query(
        query=query, params={"node_uuid": node_uuid, "attr_name": attr_name, "branch_name": branch_name}
    )
    if not results:
        return None
    return results[0]["value"]


def _node_query(kind: str) -> str:
    return f"""
query NodeById($ids: [ID]) {{
    {kind}(ids: $ids) {{
        count
        edges {{
            node {{
                id
                hfid
                display_label
            }}
        }}
    }}
}}
"""


class TestMigration071(TestInfrahubApp):
    @pytest.fixture(scope="class", autouse=True)
    async def normalized_kind_schema(
        self, db: InfrahubDatabase, default_branch: Branch, register_core_schema: SchemaBranch
    ) -> SchemaBranch:
        return registry.schema.register_schema(schema=_schema_root(), branch=default_branch.name)

    async def _stage_default_node(self, db: InfrahubDatabase, case: NormalizedKindCase, name: str) -> Node:
        """Create a node on the default branch, then stale its HFID and display_label to mimic the pre-fix state."""
        node = await Node.init(db=db, schema=case.kind)
        new_kwargs: dict[str, Any] = {"name": name, case.attr_name: case.raw_value}
        await node.new(db=db, **new_kwargs)
        await node.save(db=db)
        # human_friendly_id is a List-kind attribute, stored as ujson.dumps(...) — see ListAttribute.serialize_value.
        await _set_attribute_value(
            db=db, node_uuid=node.id, attr_name="human_friendly_id", value=ujson.dumps([case.raw_value])
        )
        await _set_attribute_value(
            db=db, node_uuid=node.id, attr_name="display_label", value=case.raw_display_label(name)
        )
        return node

    async def _query_node(self, db: InfrahubDatabase, branch: Branch, kind: str, node_id: str) -> dict[str, Any]:
        gql_params = await prepare_graphql_params(db=db, branch=branch)
        result = await graphql(
            schema=gql_params.schema,
            source=_node_query(kind),
            context_value=gql_params.context,
            root_value=None,
            variable_values={"ids": [node_id]},
        )
        assert result.errors is None, result.errors
        assert result.data is not None
        assert result.data[kind]["count"] == 1
        return result.data[kind]["edges"][0]["node"]

    async def test_migration_071_recomputes_hfid_and_display_label(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        normalized_kind_schema: SchemaBranch,
    ) -> None:
        """Stage every case at once, run the migration once, then verify each case."""
        nodes: dict[str, tuple[Node, str]] = {}
        for case in CASES:
            node = await self._stage_default_node(db=db, case=case, name=case.node_name)
            nodes[case.kind] = (node, case.node_name)

        default_branch.update_schema_hash()
        for case in CASES:
            node, name = nodes[case.kind]
            edge = await self._query_node(db=db, branch=default_branch, kind=case.kind, node_id=node.id)
            assert edge["hfid"] == [case.raw_value]
            assert edge["display_label"] == case.raw_display_label(name)

        async with db.start_session() as dbs:
            migration = Migration071()
            execution_result = await migration.execute(migration_input=MigrationInput(db=dbs))
            assert not execution_result.errors, execution_result.errors

            validation_result = await migration.validate_migration(db=dbs)
            assert not validation_result.errors

        for case in CASES:
            node, name = nodes[case.kind]
            assert await _read_attribute_value(db=db, node_uuid=node.id, attr_name="human_friendly_id") == ujson.dumps(
                [case.canonical_value]
            )
            assert await _read_attribute_value(
                db=db, node_uuid=node.id, attr_name="display_label"
            ) == case.canonical_display_label(name)
            edge = await self._query_node(db=db, branch=default_branch, kind=case.kind, node_id=node.id)
            assert edge["id"] == node.id
            assert edge["hfid"] == [case.canonical_value]
            assert edge["display_label"] == case.canonical_display_label(name)

    async def test_migration_071_idempotent(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        normalized_kind_schema: SchemaBranch,
    ) -> None:
        # Run once on a freshly-staled node, then again — second run must leave the value unchanged.
        case = CASES[0]
        node = await Node.init(db=db, schema=case.kind)
        new_kwargs: dict[str, Any] = {"name": f"{case.node_name}-idem", case.attr_name: case.raw_value}
        await node.new(db=db, **new_kwargs)
        await node.save(db=db)

        await _set_attribute_value(
            db=db, node_uuid=node.id, attr_name="human_friendly_id", value=ujson.dumps([case.raw_value])
        )

        async with db.start_session() as dbs:
            await Migration071().execute(migration_input=MigrationInput(db=dbs))

        first_pass = await _read_attribute_value(db=db, node_uuid=node.id, attr_name="human_friendly_id")

        async with db.start_session() as dbs:
            result = await Migration071().execute(migration_input=MigrationInput(db=dbs))
            assert not result.errors

        second_pass = await _read_attribute_value(db=db, node_uuid=node.id, attr_name="human_friendly_id")

        assert first_pass == second_pass == ujson.dumps([case.canonical_value])

    async def test_migration_071_execute_against_branch(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        normalized_kind_schema: SchemaBranch,
    ) -> None:
        test_branch = await create_branch(db=db, branch_name="test-branch-m071")

        nodes: dict[str, tuple[Node, str]] = {}
        for case in CASES:
            node_name = f"{case.node_name}-branch"
            node = await Node.init(db=db, schema=case.kind, branch=test_branch)
            new_kwargs: dict[str, Any] = {"name": node_name, case.attr_name: case.raw_value}
            await node.new(db=db, **new_kwargs)
            await node.save(db=db)

            # Mimic the pre-fix state on the branch: HFID/display_label rendered from raw user input.
            await _set_attribute_value_on_branch(
                db=db,
                node_uuid=node.id,
                attr_name="human_friendly_id",
                value=ujson.dumps([case.raw_value]),
                branch_name=test_branch.name,
            )
            await _set_attribute_value_on_branch(
                db=db,
                node_uuid=node.id,
                attr_name="display_label",
                value=case.raw_display_label(node_name),
                branch_name=test_branch.name,
            )
            nodes[case.kind] = (node, node_name)

        # Execute against default branch first (required before execute_against_branch)
        async with db.start_session() as dbs:
            await Migration071().execute(migration_input=MigrationInput(db=dbs))

        await test_branch.rebase(db=db)

        async with db.start_session() as dbs:
            result = await Migration071().execute_against_branch(
                migration_input=MigrationInput(db=dbs), branch=test_branch
            )
            assert not result.errors, result.errors

        for case in CASES:
            node, node_name = nodes[case.kind]
            assert await _read_attribute_value_on_branch(
                db=db, node_uuid=node.id, attr_name="human_friendly_id", branch_name=test_branch.name
            ) == ujson.dumps([case.canonical_value])
            assert await _read_attribute_value_on_branch(
                db=db, node_uuid=node.id, attr_name="display_label", branch_name=test_branch.name
            ) == case.canonical_display_label(node_name)
