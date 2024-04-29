from infrahub.core import registry
from infrahub.core.manager import NodeManager
from infrahub.database import InfrahubDatabase

CHECK_HIERARCHY_QUERY = """
MATCH ({uuid: $node_uuid})-[rel:IS_RELATED]-(rel_node:Relationship {name: "parent__child"})
RETURN rel
"""


async def test_update_node_with_hierarchy(db: InfrahubDatabase, hierarchical_location_data):
    site_schema = registry.schema.get(name="LocationSite", duplicate=False)
    retrieved_node = await NodeManager.get_one(db=db, id=hierarchical_location_data["seattle"].id)
    new_parent = await NodeManager.get_one(db=db, id=hierarchical_location_data["europe"].id)
    results = await db.execute_query(
        query=CHECK_HIERARCHY_QUERY, params={"node_uuid": hierarchical_location_data["seattle"].id}
    )
    for result in results:
        assert result.get("rel").get("hierarchy") == site_schema.hierarchy

    await retrieved_node.parent.update(db=db, data=new_parent)
    await retrieved_node.save(db=db)

    updated_node = await NodeManager.get_one(db=db, id=retrieved_node.id)
    parent_rels = await updated_node.parent.get_relationships(db=db)
    assert len(parent_rels) == 1
    assert parent_rels[0].peer_id == new_parent.id

    results = await db.execute_query(query=CHECK_HIERARCHY_QUERY, params={"node_uuid": updated_node.id})
    for result in results:
        assert result.get("rel").get("hierarchy") == site_schema.hierarchy
