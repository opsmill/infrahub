from infrahub.core.branch.models import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.graph.m054_cleanup_orphaned_nodes import Migration054
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase


async def test_migration_054(
    db: InfrahubDatabase,
    default_branch: Branch,
    branch_aware_node_with_agnostic_attrs_schema: SchemaBranch,
) -> None:
    """Test cleanup of orphaned nodes with branch-agnostic attributes and relationships."""
    branch = await create_branch(db=db, branch_name="orphan-branch")

    # Create a Site on main branch (non-orphaned, will be referenced by relationships)
    site = await Node.init(db=db, branch=default_branch, schema="TestSite")
    await site.new(db=db, name="TestSite")
    await site.save(db=db)

    # Create a Device on main branch (non-orphaned, should be preserved)
    device_preserved = await Node.init(db=db, branch=default_branch, schema="TestDevice")
    await device_preserved.new(db=db, name="PreservedDevice", serial_number="SN-KEEP", site=site)
    await device_preserved.save(db=db)

    # Create a Device on branch with agnostic attribute (will be orphaned)
    device_orphan_attr = await Node.init(db=db, branch=branch, schema="TestDevice")
    await device_orphan_attr.new(db=db, name="OrphanAttrDevice", serial_number="SN-ORPHAN")
    await device_orphan_attr.save(db=db)

    # Create a Device on branch with agnostic relationship (will be orphaned)
    device_orphan_rel = await Node.init(db=db, branch=branch, schema="TestDevice")
    await device_orphan_rel.new(db=db, name="OrphanRelDevice", site=site)
    await device_orphan_rel.save(db=db)

    # Capture UUIDs
    site_uuid = site.id
    preserved_uuid = device_preserved.id

    orphan_attr_uuid = device_orphan_attr.id
    orphan_attr_serial_uuid = device_orphan_attr.get_attribute("serial_number").id
    orphan_rel_uuid = device_orphan_rel.id
    orphan_rel_site = await device_orphan_rel.get_relationship("site").get(db=db)
    orphan_rel_site_uuid = orphan_rel_site.id

    # Orphan the devices by deleting their IS_PART_OF edges
    delete_query = """
    MATCH (n:Node)-[r:IS_PART_OF]->(:Root)
    WHERE n.uuid IN $uuids
    DELETE r
    """
    await db.execute_query(query=delete_query, params={"uuids": [orphan_attr_uuid, orphan_rel_uuid]})

    # Run the migration
    migration = Migration054()
    execution_result = await migration.execute(migration_input=MigrationInput(db=db))
    assert not execution_result.errors

    # Verify orphaned nodes are deleted
    node_query = """
    MATCH (n:Node {uuid: $uuid})
    RETURN n
    """
    result = await db.execute_query(query=node_query, params={"uuid": orphan_attr_uuid})
    assert len(result) == 0, "Orphaned node with agnostic attr should be deleted"

    result = await db.execute_query(query=node_query, params={"uuid": orphan_rel_uuid})
    assert len(result) == 0, "Orphaned node with agnostic rel should be deleted"

    # Verify orphaned node's attribute is deleted
    attr_query = """
    MATCH (a:Attribute {uuid: $uuid})
    RETURN a
    """
    result = await db.execute_query(query=attr_query, params={"uuid": orphan_attr_serial_uuid})
    assert len(result) == 0, "Attribute of orphaned node should be deleted"

    # Verify orphaned node's relationship is deleted (had only 1 valid peer)
    rel_query = """
    MATCH (r:Relationship {uuid: $uuid})
    RETURN r
    """
    result = await db.execute_query(query=rel_query, params={"uuid": orphan_rel_site_uuid})
    assert len(result) == 0, "Relationship with < 2 peers should be deleted"

    # Verify non-orphaned nodes are preserved
    retrieved_site = await NodeManager.get_one(db=db, branch=default_branch, id=site_uuid)
    assert retrieved_site is not None, "Non-orphaned site should still exist"

    retrieved_preserved = await NodeManager.get_one(db=db, branch=default_branch, id=preserved_uuid)
    assert retrieved_preserved is not None, "Non-orphaned device should still exist"
    assert retrieved_preserved.get_attribute("serial_number").value == "SN-KEEP"
    retrieved_rel = await retrieved_preserved.get_relationship("site").get(db=db)
    assert retrieved_rel is not None, "Relationship with 2 valid peers should still exist"
    assert retrieved_rel.get_peer_id() == site.id
