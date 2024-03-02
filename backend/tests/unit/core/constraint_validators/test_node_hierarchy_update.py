from typing import Dict
from infrahub_sdk import InfrahubClient

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import PathType, SchemaPathType
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.path import DataPath, SchemaPath
from infrahub.core.validators.node.hierarchy import NodeHierarchyChecker, NodeHierarchyUpdateValidatorQuery
from infrahub.core.validators.model import SchemaConstraintValidatorRequest
from infrahub.database import InfrahubDatabase
from infrahub.message_bus.messages import SchemaValidatorPathResponse
from infrahub.message_bus.messages.schema_validator_path import SchemaValidatorPath
from infrahub.services import InfrahubServices
import pytest


@pytest.fixture
async def hierarchical_location_data_simple_and_small(db: InfrahubDatabase, hierarchical_location_schema_simple) -> Dict[str, Node]:
    REGIONS = (
        ("north-america",),
        ("europe",),
        ("asia",),
    )

    SITES = (
        ("paris", "europe"),
        ("london", "europe"),
        ("chicago", "north-america"),
        ("seattle", "north-america"),
        ("beijing", "asia"),
        ("singapore", "asia"),
    )

    nodes = {}

    r1 = await Node.init(db=db, schema="LocationRegion")
    await r1.new(db=db, name="r1")
    await r1.save(db=db)
    nodes[r1.name.value] = r1
    r2 = await Node.init(db=db, schema="LocationRegion")
    await r2.new(db=db, name="r2")
    await r2.save(db=db)
    nodes[r2.name.value] = r2
    s1r1 = await Node.init(db=db, schema="LocationSite")
    await s1r1.new(db=db, name="s1r1", parent=r1)
    await s1r1.save(db=db)
    nodes[s1r1.name.value] = s1r1
    s1r1_rack = await Node.init(db=db, schema="LocationRack")
    await s1r1_rack.new(db=db, name="s1r1_rack", parent=s1r1, status="online")
    await s1r1_rack.save(db=db)
    nodes[s1r1_rack.name.value] = s1r1_rack
    s2r1 = await Node.init(db=db, schema="LocationSite")
    await s2r1.new(db=db, name="s2r1", parent=r1)
    await s2r1.save(db=db)
    nodes[s2r1.name.value] = s2r1
    s2r1_rack = await Node.init(db=db, schema="LocationRack")
    await s2r1_rack.new(db=db, name="s2r1_rack", parent=s2r1, status="online")
    await s2r1_rack.save(db=db)
    nodes[s2r1_rack.name.value] = s2r1_rack
    s1r2 = await Node.init(db=db, schema="LocationSite")
    await s1r2.new(db=db, name="s1r2", parent=r2)
    await s1r2.save(db=db)
    nodes[s1r2.name.value] = s1r2
    s1r2_rack = await Node.init(db=db, schema="LocationRack")
    await s1r2_rack.new(db=db, name="s1r2_rack", parent=s1r2, status="online")
    await s1r2_rack.save(db=db)
    nodes[s1r2_rack.name.value] = s1r2_rack
    s2r2 = await Node.init(db=db, schema="LocationSite")
    await s2r2.new(db=db, name="s2r2", parent=r2)
    await s2r2.save(db=db)
    nodes[s2r2.name.value] = s2r2
    s2r2_rack = await Node.init(db=db, schema="LocationRack")
    await s2r2_rack.new(db=db, name="s2r2_rack", parent=s2r2, status="online")
    await s2r2_rack.save(db=db)
    nodes[s2r2_rack.name.value] = s2r2_rack

    return nodes

async def test_query_children_success(
    db: InfrahubDatabase, default_branch: Branch, hierarchical_location_data_simple
):
    site_schema = registry.schema.get(name="LocationSite")
    schema_path = SchemaPath(path_type=SchemaPathType.NODE, schema_kind="LocationSite", field_name="children")

    query = await NodeHierarchyUpdateValidatorQuery.init(
        db=db, branch=default_branch, node_schema=site_schema, schema_path=schema_path, check_children=True
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert len(all_data_paths) == 0

async def test_query_parent_success(
    db: InfrahubDatabase, default_branch: Branch, hierarchical_location_data_simple
):
    site_schema = registry.schema.get(name="LocationSite")
    schema_path = SchemaPath(path_type=SchemaPathType.NODE, schema_kind="LocationSite", field_name="parent")

    query = await NodeHierarchyUpdateValidatorQuery.init(
        db=db, branch=default_branch, node_schema=site_schema, schema_path=schema_path, check_parent=True
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert len(all_data_paths) == 0

async def test_query_children_failure(
    db: InfrahubDatabase, default_branch: Branch, hierarchical_location_data_simple_and_small
):
    site_schema = registry.schema.get(name="LocationSite")
    site_schema.children = "LocationRegion"

    schema_path = SchemaPath(path_type=SchemaPathType.NODE, schema_kind="LocationSite", field_name="children")

    query = await NodeHierarchyUpdateValidatorQuery.init(
        db=db, branch=default_branch, node_schema=site_schema, schema_path=schema_path, check_children=True
    )

    await query.execute(db=db)

    grouped_paths = await query.get_paths()
    all_data_paths = grouped_paths.get_all_data_paths()
    assert len(all_data_paths) == 4
    assert DataPath(
        # TODO
    ) in all_data_paths

# more tests here