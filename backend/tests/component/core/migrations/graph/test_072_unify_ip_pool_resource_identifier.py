import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.graph.m072_unify_ip_pool_resource_identifier import (
    NEW_IDENTIFIER,
    Migration072,
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


async def _get_pool_labels(db: InfrahubDatabase) -> dict[str, list[str]]:
    """Return ``{pool_kind: [neo4j_labels...]}`` for every existing pool vertex."""
    query = """
MATCH (n:CoreIPPrefixPool|CoreIPAddressPool)
RETURN n.kind AS kind, labels(n) AS labels
ORDER BY n.kind
    """
    rows = await db.execute_query(query=query)
    return {row["kind"]: list(row["labels"]) for row in rows}


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


async def test_migration_072(
    db: InfrahubDatabase,
    reset_registry: None,
    default_branch: Branch,
    pre_migration_schema_db: SchemaBranch,
) -> None:
    # ---------------------------------------------------------------------
    # 1. Create data for pre-migration schema
    # ---------------------------------------------------------------------
    ip_namespace = await Node.init(db=db, schema=InfrahubKind.NAMESPACE)
    await ip_namespace.new(db=db, name="default")
    await ip_namespace.save(db=db)
    registry.default_ipnamespace = ip_namespace.id

    ip_prefix = await Node.init(db=db, schema="IpamIPPrefix")
    await ip_prefix.new(db=db, prefix="10.0.0.0/8", ip_namespace=ip_namespace)
    await ip_prefix.save(db=db)

    prefix_pool_schema = registry.schema.get_node_schema(
        name=InfrahubKind.IPPREFIXPOOL, branch=default_branch, duplicate=False
    )
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

    address_pool_schema = registry.schema.get_node_schema(
        name=InfrahubKind.IPADDRESSPOOL, branch=default_branch, duplicate=False
    )
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
    # 2. Verify the pre-migration schema shape
    # ---------------------------------------------------------------------
    pre_schema = await registry.schema.load_schema_from_db(db=db, branch=default_branch)

    assert InfrahubKind.IPPOOL not in pre_schema.generics

    pre_prefix_pool_node = pre_schema.get_node(name=InfrahubKind.IPPREFIXPOOL, duplicate=False)
    assert InfrahubKind.IPPOOL not in pre_prefix_pool_node.inherit_from
    assert pre_prefix_pool_node.get_relationship(name="resources").identifier == "prefixpool__resource"

    pre_address_pool_node = pre_schema.get_node(name=InfrahubKind.IPADDRESSPOOL, duplicate=False)
    assert InfrahubKind.IPPOOL not in pre_address_pool_node.inherit_from
    assert pre_address_pool_node.get_relationship(name="resources").identifier == "ipaddresspool__resource"

    pre_builtin_prefix = pre_schema.get_generic(name=InfrahubKind.IPPREFIX, duplicate=False)
    pre_resource_pool_rel = pre_builtin_prefix.get_relationship(name="resource_pool")
    assert pre_resource_pool_rel.identifier == "ipaddresspool__resource"
    assert pre_resource_pool_rel.peer == InfrahubKind.IPADDRESSPOOL

    pre_pool_labels = await _get_pool_labels(db)
    assert "CoreIPPool" not in pre_pool_labels[InfrahubKind.IPPREFIXPOOL]
    assert "CoreIPPool" not in pre_pool_labels[InfrahubKind.IPADDRESSPOOL]

    # verify that only the address pool instance is visible from the prefix at this point
    pre_loaded_prefix = await NodeManager.get_one(db=db, id=ip_prefix.id)
    assert pre_loaded_prefix is not None
    pre_peer_ids = {
        r.peer_id for r in await pre_loaded_prefix.get_relationship(name="resource_pool").get_relationships(db=db)
    }
    assert pre_peer_ids == {address_pool.id}

    # ---------------------------------------------------------------------
    # 3. Run the migration.
    # ---------------------------------------------------------------------
    migration = Migration072.init()
    execution_result = await migration.execute(migration_input=MigrationInput(db=db))
    assert not execution_result.errors, execution_result.errors

    validation_result = await migration.validate_migration(db=db)
    assert not validation_result.errors, validation_result.errors

    # ---------------------------------------------------------------------
    # 4. Verify the post-migration shape via the schema loaded from the DB.
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

    post_pool_labels = await _get_pool_labels(db)
    assert "CoreIPPool" in post_pool_labels[InfrahubKind.IPPREFIXPOOL]
    assert "CoreIPPool" in post_pool_labels[InfrahubKind.IPADDRESSPOOL]

    # ---------------------------------------------------------------------
    # 5. Verify high-level objects through NodeManager — both pools must now be
    #    visible on the prefix's resource_pool relationship.
    # ---------------------------------------------------------------------
    loaded_prefix = await NodeManager.get_one(db=db, id=ip_prefix.id)
    assert loaded_prefix is not None
    peer_ids = {r.peer_id for r in await loaded_prefix.get_relationship(name="resource_pool").get_relationships(db=db)}
    assert peer_ids == {prefix_pool.id, address_pool.id}

    loaded_prefix_pool = await NodeManager.get_one(db=db, id=prefix_pool.id)
    assert loaded_prefix_pool is not None
    assert loaded_prefix_pool.get_kind() == InfrahubKind.IPPREFIXPOOL
    prefix_pool_resource_ids = {
        r.peer_id for r in await loaded_prefix_pool.get_relationship(name="resources").get_relationships(db=db)
    }
    assert prefix_pool_resource_ids == {ip_prefix.id}

    loaded_address_pool = await NodeManager.get_one(db=db, id=address_pool.id)
    assert loaded_address_pool is not None
    assert loaded_address_pool.get_kind() == InfrahubKind.IPADDRESSPOOL
    address_pool_resource_ids = {
        r.peer_id for r in await loaded_address_pool.get_relationship(name="resources").get_relationships(db=db)
    }
    assert address_pool_resource_ids == {ip_prefix.id}

    # ---------------------------------------------------------------------
    # 6. Run the graph integrity checks.
    # ---------------------------------------------------------------------
    await verify_graph(db=db)


async def test_migration_072_is_idempotent(
    db: InfrahubDatabase,
    reset_registry: None,
    default_branch: Branch,
    register_core_schema_db: None,
) -> None:
    migration = Migration072.init()

    first = await migration.execute(migration_input=MigrationInput(db=db))
    assert not first.errors, first.errors

    second = await migration.execute(migration_input=MigrationInput(db=db))
    assert not second.errors, second.errors

    validation_result = await migration.validate_migration(db=db)
    assert not validation_result.errors, validation_result.errors

    await verify_graph(db=db)
