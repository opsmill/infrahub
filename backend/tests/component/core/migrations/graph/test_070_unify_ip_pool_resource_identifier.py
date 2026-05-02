from dataclasses import dataclass

import pytest
import ujson

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.graph.m070_unify_ip_pool_resource_identifier import (
    NEW_IDENTIFIER,
    OLD_IDENTIFIERS,
    Migration070,
)
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.node.resource_manager.ip_address_pool import CoreIPAddressPool
from infrahub.core.node.resource_manager.ip_prefix_pool import CoreIPPrefixPool
from infrahub.core.schema import SchemaRoot, core_models
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from tests.helpers.db_validation import verify_graph

# ---------------------------------------------------------------------------
# Typed result types — what the helpers below return so each assertion reads
# as a typed Python check rather than dict-key indexing.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PoolLabelRow:
    kind: str
    labels: list[str]


# ---------------------------------------------------------------------------
# Helpers — each one owns the Cypher it runs and converts the result into a
# typed primitive or dataclass before returning.
# ---------------------------------------------------------------------------


async def _count_pool_relationships_by_name(db: InfrahubDatabase, names: list[str]) -> dict[str, int]:
    query = """
MATCH (pool:CoreIPPrefixPool|CoreIPAddressPool)-[:IS_RELATED]-(r:Relationship)-[:IS_RELATED]-(:BuiltinIPPrefix)
WHERE r.name IN $names
WITH DISTINCT r
RETURN r.name AS name, count(r) AS total
    """
    rows = await db.execute_query(query=query, params={"names": names})
    return {row["name"]: int(row["total"]) for row in rows}


async def _get_pool_label_rows(db: InfrahubDatabase) -> list[PoolLabelRow]:
    query = """
MATCH (n:CoreIPPrefixPool|CoreIPAddressPool)
RETURN labels(n) AS labels, n.kind AS kind
ORDER BY n.kind
    """
    rows = await db.execute_query(query=query)
    return [PoolLabelRow(kind=row["kind"], labels=list(row["labels"])) for row in rows]


async def _count_core_ip_pool_generic(db: InfrahubDatabase) -> int:
    query = """
MATCH (g:SchemaGeneric)-[:HAS_ATTRIBUTE]->(:Attribute {name: "name"})-[:HAS_VALUE]->(v)
WHERE v.value = "IPPool"
RETURN count(g) AS total
    """
    rows = await db.execute_query(query=query)
    return int(rows[0]["total"]) if rows else 0


async def _get_inherit_from_value(db: InfrahubDatabase, node_name: str) -> list[str]:
    query = """
MATCH (sn:SchemaNode)-[:HAS_ATTRIBUTE]->(:Attribute {name: "name"})-[:HAS_VALUE]->(v_name)
WHERE v_name.value = $node_name
MATCH (sn)-[:HAS_ATTRIBUTE]->(:Attribute {name: "namespace"})-[:HAS_VALUE]->(v_ns)
WHERE v_ns.value = "Core"
MATCH (sn)-[:HAS_ATTRIBUTE]->(:Attribute {name: "inherit_from"})-[:HAS_VALUE]->(av:AttributeValue)
RETURN av.value AS value
    """
    rows = await db.execute_query(query=query, params={"node_name": node_name})
    if not rows:
        return []
    return list(ujson.loads(rows[0]["value"]))


async def _get_schema_relationship_attribute_value(
    db: InfrahubDatabase,
    parent_name: str,
    parent_namespace: str,
    relationship_name: str,
    attribute_name: str,
) -> str:
    query = """
MATCH (parent)-[:HAS_ATTRIBUTE]->(:Attribute {name: "name"})-[:HAS_VALUE]->(v_kind)
WHERE v_kind.value = $parent_name
MATCH (parent)-[:HAS_ATTRIBUTE]->(:Attribute {name: "namespace"})-[:HAS_VALUE]->(v_ns)
WHERE v_ns.value = $parent_namespace
MATCH (parent)-[:IS_RELATED]-(:Relationship)-[:IS_RELATED]-(sr:SchemaRelationship)
    -[:HAS_ATTRIBUTE]->(:Attribute {name: "name"})-[:HAS_VALUE]->(v_rel)
WHERE v_rel.value = $relationship_name
MATCH (sr)-[:HAS_ATTRIBUTE]->(:Attribute {name: $attribute_name})-[:HAS_VALUE]->(av:AttributeValue)
RETURN av.value AS value
    """
    rows = await db.execute_query(
        query=query,
        params={
            "parent_name": parent_name,
            "parent_namespace": parent_namespace,
            "relationship_name": relationship_name,
            "attribute_name": attribute_name,
        },
    )
    return str(rows[0]["value"])


def _downgrade_schema(schema_branch: SchemaBranch) -> None:
    """Mutate the in-memory schema back to the pre-migration shape, before processing.

    This is what gets persisted to the DB so the rest of the test exercises a
    realistic pre-migration starting state without any post-load Cypher rewrites.
    """
    # 1. Drop the new CoreIPPool generic.
    if InfrahubKind.IPPOOL in schema_branch.generics:
        schema_branch.delete(name=InfrahubKind.IPPOOL)

    # 2. Strip CoreIPPool from inherit_from on both pool NodeSchemas + revert
    #    their `resources` identifier to the old per-pool name.
    for pool_kind, old_identifier in (
        (InfrahubKind.IPPREFIXPOOL, "prefixpool__resource"),
        (InfrahubKind.IPADDRESSPOOL, "ipaddresspool__resource"),
    ):
        pool = schema_branch.get_node(name=pool_kind, duplicate=False)
        pool.inherit_from = [k for k in pool.inherit_from if k != InfrahubKind.IPPOOL]
        resources = pool.get_relationship(name="resources")
        resources.identifier = old_identifier

    # 3. Revert BuiltinIPPrefix.resource_pool to its old peer + identifier.
    builtin_prefix = schema_branch.get_generic(name=InfrahubKind.IPPREFIX, duplicate=False)
    rp_rel = builtin_prefix.get_relationship(name="resource_pool")
    rp_rel.peer = InfrahubKind.IPADDRESSPOOL
    rp_rel.identifier = "ipaddresspool__resource"


@pytest.fixture
async def pre_migration_schema_db(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_internal_models_schema: SchemaBranch,
    ipam_schema: SchemaRoot,
) -> SchemaBranch:
    """Persist a downgraded core schema (+ concrete IPAM nodes) to the database.

    Mirrors :func:`do_register_core_models_schema` but runs the in-memory downgrade
    between ``load_schema`` and ``process`` so the SchemaBranch is validated in its
    pre-migration shape and persisted as such. The IPAM concrete nodes come from the
    shared ``ipam_schema`` fixture.
    """
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    schema_branch.load_schema(schema=SchemaRoot(**core_models))
    _downgrade_schema(schema_branch)
    schema_branch.load_schema(schema=ipam_schema)
    schema_branch.process()
    default_branch.update_schema_hash()

    await registry.schema.load_schema_to_db(schema=schema_branch, branch=default_branch, db=db, at=Timestamp())
    updated_schema = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
    registry.schema.set_schema_branch(name=default_branch.name, schema=updated_schema)
    return updated_schema


async def test_migration_070(
    db: InfrahubDatabase,
    reset_registry: None,
    default_branch: Branch,
    pre_migration_schema_db: SchemaBranch,
) -> None:
    # ---------------------------------------------------------------------
    # 1. Create data using NodeManager / ORM-style Node objects.  The DB is
    #    in pre-migration shape, so the resources relationship identifiers
    #    naturally land on the old `prefixpool__resource` / `ipaddresspool__resource`.
    # ---------------------------------------------------------------------
    ip_namespace = await Node.init(db=db, schema=InfrahubKind.NAMESPACE)
    await ip_namespace.new(db=db, name="default")
    await ip_namespace.save(db=db)
    registry.default_ipnamespace = ip_namespace.id

    ip_prefix = await Node.init(db=db, schema="IpamIPPrefix")
    await ip_prefix.new(db=db, prefix="10.0.0.0/8", ip_namespace=ip_namespace)
    await ip_prefix.save(db=db)

    prefix_pool_schema = registry.schema.get_node_schema(name=InfrahubKind.IPPREFIXPOOL, branch=default_branch)
    prefix_pool = await CoreIPPrefixPool.init(schema=prefix_pool_schema, db=db)
    await prefix_pool.new(
        db=db,
        name="test-prefix-pool",
        default_prefix_length=24,
        default_prefix_type="IpamIPPrefix",
        resources=[ip_prefix],
        ip_namespace=ip_namespace,
    )
    await prefix_pool.save(db=db)

    address_pool_schema = registry.schema.get_node_schema(name=InfrahubKind.IPADDRESSPOOL, branch=default_branch)
    address_pool = await CoreIPAddressPool.init(schema=address_pool_schema, db=db)
    await address_pool.new(
        db=db,
        name="test-address-pool",
        default_address_type="IpamIPAddress",
        resources=[ip_prefix],
        ip_namespace=ip_namespace,
    )
    await address_pool.save(db=db)

    # ---------------------------------------------------------------------
    # 2. Verify pre-migration shape via Cypher (data + schema graph).
    # ---------------------------------------------------------------------
    pre_counts = await _count_pool_relationships_by_name(db, OLD_IDENTIFIERS + [NEW_IDENTIFIER])
    assert pre_counts.get("prefixpool__resource", 0) == 1
    assert pre_counts.get("ipaddresspool__resource", 0) == 1
    assert pre_counts.get(NEW_IDENTIFIER, 0) == 0

    for row in await _get_pool_label_rows(db):
        assert "CoreIPPool" not in row.labels, f"{row.kind} unexpectedly already has :CoreIPPool ({row.labels})"

    assert await _count_core_ip_pool_generic(db) == 0

    assert InfrahubKind.IPPOOL not in await _get_inherit_from_value(db, node_name="IPPrefixPool")
    assert InfrahubKind.IPPOOL not in await _get_inherit_from_value(db, node_name="IPAddressPool")

    assert (
        await _get_schema_relationship_attribute_value(
            db,
            parent_name="IPPrefixPool",
            parent_namespace="Core",
            relationship_name="resources",
            attribute_name="identifier",
        )
        == "prefixpool__resource"
    )
    assert (
        await _get_schema_relationship_attribute_value(
            db,
            parent_name="IPAddressPool",
            parent_namespace="Core",
            relationship_name="resources",
            attribute_name="identifier",
        )
        == "ipaddresspool__resource"
    )
    assert (
        await _get_schema_relationship_attribute_value(
            db,
            parent_name="IPPrefix",
            parent_namespace="Builtin",
            relationship_name="resource_pool",
            attribute_name="identifier",
        )
        == "ipaddresspool__resource"
    )
    assert (
        await _get_schema_relationship_attribute_value(
            db,
            parent_name="IPPrefix",
            parent_namespace="Builtin",
            relationship_name="resource_pool",
            attribute_name="peer",
        )
        == InfrahubKind.IPADDRESSPOOL
    )

    # ---------------------------------------------------------------------
    # 3. Run the migration.
    # ---------------------------------------------------------------------
    migration = Migration070.init()
    execution_result = await migration.execute(migration_input=MigrationInput(db=db))
    assert not execution_result.errors, execution_result.errors

    validation_result = await migration.validate_migration(db=db)
    assert not validation_result.errors, validation_result.errors

    # ---------------------------------------------------------------------
    # 4. Verify post-migration shape via Cypher.
    # ---------------------------------------------------------------------
    post_counts = await _count_pool_relationships_by_name(db, OLD_IDENTIFIERS + [NEW_IDENTIFIER])
    assert post_counts.get(NEW_IDENTIFIER, 0) == 2
    assert post_counts.get("prefixpool__resource", 0) == 0
    assert post_counts.get("ipaddresspool__resource", 0) == 0

    pool_labels = await _get_pool_label_rows(db)
    assert pool_labels
    for row in pool_labels:
        assert "CoreIPPool" in row.labels, f"{row.kind} missing :CoreIPPool after migration ({row.labels})"

    assert await _count_core_ip_pool_generic(db) >= 1

    assert InfrahubKind.IPPOOL in await _get_inherit_from_value(db, node_name="IPPrefixPool")
    assert InfrahubKind.IPPOOL in await _get_inherit_from_value(db, node_name="IPAddressPool")

    assert (
        await _get_schema_relationship_attribute_value(
            db,
            parent_name="IPPrefixPool",
            parent_namespace="Core",
            relationship_name="resources",
            attribute_name="identifier",
        )
        == NEW_IDENTIFIER
    )
    assert (
        await _get_schema_relationship_attribute_value(
            db,
            parent_name="IPAddressPool",
            parent_namespace="Core",
            relationship_name="resources",
            attribute_name="identifier",
        )
        == NEW_IDENTIFIER
    )
    assert (
        await _get_schema_relationship_attribute_value(
            db,
            parent_name="IPPrefix",
            parent_namespace="Builtin",
            relationship_name="resource_pool",
            attribute_name="identifier",
        )
        == NEW_IDENTIFIER
    )
    assert (
        await _get_schema_relationship_attribute_value(
            db,
            parent_name="IPPrefix",
            parent_namespace="Builtin",
            relationship_name="resource_pool",
            attribute_name="peer",
        )
        == InfrahubKind.IPPOOL
    )

    # ---------------------------------------------------------------------
    # 5. Reload the schema from the database and verify the high-level shape.
    # ---------------------------------------------------------------------
    reloaded = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
    registry.schema.set_schema_branch(name=default_branch.name, schema=reloaded)

    ip_pool_generic = reloaded.get_generic(name=InfrahubKind.IPPOOL, duplicate=False)
    assert ip_pool_generic.kind == InfrahubKind.IPPOOL
    assert ip_pool_generic.namespace == "Core"

    prefix_pool_node = reloaded.get_node(name=InfrahubKind.IPPREFIXPOOL, duplicate=False)
    assert InfrahubKind.IPPOOL in prefix_pool_node.inherit_from
    assert prefix_pool_node.get_relationship(name="resources").identifier == NEW_IDENTIFIER

    address_pool_node = reloaded.get_node(name=InfrahubKind.IPADDRESSPOOL, duplicate=False)
    assert InfrahubKind.IPPOOL in address_pool_node.inherit_from
    assert address_pool_node.get_relationship(name="resources").identifier == NEW_IDENTIFIER

    builtin_prefix = reloaded.get_generic(name=InfrahubKind.IPPREFIX, duplicate=False)
    resource_pool_rel = builtin_prefix.get_relationship(name="resource_pool")
    assert resource_pool_rel.identifier == NEW_IDENTIFIER
    assert resource_pool_rel.peer == InfrahubKind.IPPOOL

    # ---------------------------------------------------------------------
    # 6. Verify high-level objects through NodeManager — both pools must be
    #    visible on the prefix's resource_pool relationship.
    # ---------------------------------------------------------------------
    loaded_prefix = await NodeManager.get_one(db=db, id=ip_prefix.id)
    assert loaded_prefix is not None
    rel_mgr = loaded_prefix.get_relationship(name="resource_pool")
    peers = await rel_mgr.get_relationships(db=db)
    peer_ids = {r.peer_id for r in peers}
    assert peer_ids == {prefix_pool.id, address_pool.id}

    loaded_prefix_pool = await NodeManager.get_one(db=db, id=prefix_pool.id)
    assert loaded_prefix_pool is not None
    assert loaded_prefix_pool.get_kind() == InfrahubKind.IPPREFIXPOOL

    loaded_address_pool = await NodeManager.get_one(db=db, id=address_pool.id)
    assert loaded_address_pool is not None
    assert loaded_address_pool.get_kind() == InfrahubKind.IPADDRESSPOOL

    # ---------------------------------------------------------------------
    # 7. Run the cross-cutting graph integrity checks.
    # ---------------------------------------------------------------------
    await verify_graph(db=db)


async def test_migration_070_is_idempotent(
    db: InfrahubDatabase,
    reset_registry: None,
    default_branch: Branch,
    register_core_schema_db: None,
) -> None:
    migration = Migration070.init()

    first = await migration.execute(migration_input=MigrationInput(db=db))
    assert not first.errors, first.errors

    second = await migration.execute(migration_input=MigrationInput(db=db))
    assert not second.errors, second.errors

    validation_result = await migration.validate_migration(db=db)
    assert not validation_result.errors, validation_result.errors

    await verify_graph(db=db)
