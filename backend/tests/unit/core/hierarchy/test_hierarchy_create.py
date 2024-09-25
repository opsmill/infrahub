import pytest

from infrahub.core import registry
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import ValidationError


async def test_create_node_with_invalid_hierarchy(db: InfrahubDatabase, hierarchical_location_data):
    region_schema = registry.schema.get_node_schema(name="LocationRegion", duplicate=True)
    rack_schema = registry.schema.get_node_schema(name="LocationRack", duplicate=True)
    europe = await NodeManager.get_one(db=db, id=hierarchical_location_data["europe"].id)
    city = await NodeManager.get_one(db=db, id=hierarchical_location_data["seattle"].id)

    with pytest.raises(ValidationError) as exc:
        region = await Node.init(db=db, schema=region_schema)
        await region.new(db=db, name="region2", parent=city)
    assert "Not supported to assign a value to parent" in str(exc.value)

    with pytest.raises(ValidationError) as exc:
        rack = await Node.init(db=db, schema=rack_schema)
        await rack.new(db=db, name="rack2", parent=city, children=[europe])
    assert "Not supported to assign some children" in str(exc.value)
