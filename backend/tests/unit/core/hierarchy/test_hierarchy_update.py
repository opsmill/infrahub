import pytest

from infrahub.core import registry
from infrahub.core.manager import NodeManager
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import ValidationError

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
    nodes = await NodeManager.query(db=db, schema=site_schema, filters={"parent__name__value": "europe"})
    assert {node.name.value for node in nodes} == {"paris", "london", "seattle"}


async def test_update_node_invalid_hierarchy(db: InfrahubDatabase, hierarchical_location_data):
    city = await NodeManager.get_one(db=db, id=hierarchical_location_data["seattle"].id, raise_on_error=True)
    region = await NodeManager.get_one(db=db, id=hierarchical_location_data["europe"].id, raise_on_error=True)
    rack = await NodeManager.get_one(db=db, id=hierarchical_location_data["paris-r1"].id, raise_on_error=True)

    with pytest.raises(ValidationError) as exc:
        await region.parent.update(db=db, data=city)
    assert "Not supported to assign a value to parent" in str(exc.value)

    with pytest.raises(ValidationError) as exc:
        await region.parent.add(db=db, data=city)
    assert "Not supported to assign a value to parent" in str(exc.value)

    with pytest.raises(ValidationError) as exc:
        await rack.children.update(db=db, data=[region])
    assert "Not supported to assign some children" in str(exc.value)

    with pytest.raises(ValidationError) as exc:
        await rack.children.update(db=db, data=[region])
    assert "Not supported to assign some children" in str(exc.value)
