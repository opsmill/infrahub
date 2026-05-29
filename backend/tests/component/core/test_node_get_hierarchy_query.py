from dataclasses import dataclass

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import RelationshipHierarchyDirection
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.query.node import NodeGetHierarchyQuery
from infrahub.database import InfrahubDatabase


@dataclass
class MetadataOrderByCase:
    name: str
    order_by_entry: str
    expected_indices: list[int]


METADATA_ORDER_BY_CASES = [
    MetadataOrderByCase(
        name="created_at_desc",
        order_by_entry="node_metadata__created_at__desc",
        expected_indices=[1, 0],
    ),
    MetadataOrderByCase(
        name="created_at_implicit_asc",
        order_by_entry="node_metadata__created_at",
        expected_indices=[0, 1],
    ),
    MetadataOrderByCase(
        name="created_at_explicit_asc",
        order_by_entry="node_metadata__created_at__asc",
        expected_indices=[0, 1],
    ),
]


async def test_NodeGetHierarchyQuery_order_by_metadata_with_direction(
    db: InfrahubDatabase,
    hierarchical_location_data_simple: dict[str, Node],
    default_branch: Branch,
) -> None:
    location_generic = registry.schema.get(name="LocationGeneric", branch=default_branch, duplicate=False)
    site_schema = registry.schema.get(name="LocationSite", branch=default_branch, duplicate=False)

    site_paris = hierarchical_location_data_simple["paris"]
    racks_in_creation_order = [
        hierarchical_location_data_simple["paris-r1"],
        hierarchical_location_data_simple["paris-r2"],
    ]

    for case in METADATA_ORDER_BY_CASES:
        location_generic.order_by = [case.order_by_entry]

        query = await NodeGetHierarchyQuery.init(
            db=db,
            direction=RelationshipHierarchyDirection.DESCENDANTS,
            node_id=site_paris.id,
            node_schema=site_schema,
            branch=default_branch,
        )
        await query.execute(db=db)

        descendant_ids = list(query.get_peer_ids())
        assert descendant_ids == [racks_in_creation_order[i].id for i in case.expected_indices], (
            f"order_by={case.order_by_entry!r} produced wrong order"
        )


async def test_NodeGetHierarchyQuery_order_by_attribute_desc(
    db: InfrahubDatabase,
    hierarchical_location_data_simple: dict[str, Node],
    default_branch: Branch,
) -> None:
    location_generic = registry.schema.get(name="LocationGeneric", branch=default_branch, duplicate=False)
    location_generic.order_by = ["name__value__desc"]

    site_schema = registry.schema.get(name="LocationSite", branch=default_branch, duplicate=False)

    site_paris = hierarchical_location_data_simple["paris"]
    paris_r1 = hierarchical_location_data_simple["paris-r1"]
    paris_r2 = hierarchical_location_data_simple["paris-r2"]

    query = await NodeGetHierarchyQuery.init(
        db=db,
        direction=RelationshipHierarchyDirection.DESCENDANTS,
        node_id=site_paris.id,
        node_schema=site_schema,
        branch=default_branch,
    )
    await query.execute(db=db)

    descendant_ids = list(query.get_peer_ids())
    assert descendant_ids == [paris_r2.id, paris_r1.id]


async def test_NodeGetHierarchyQuery_order_by_uuid_tiebreaker(
    db: InfrahubDatabase,
    hierarchical_location_data_simple: dict[str, Node],
    default_branch: Branch,
) -> None:
    location_generic = registry.schema.get(name="LocationGeneric", branch=default_branch, duplicate=False)
    location_generic.order_by = ["status__value__asc"]

    site_schema = registry.schema.get(name="LocationSite", branch=default_branch, duplicate=False)

    site_paris = hierarchical_location_data_simple["paris"]
    paris_r1 = hierarchical_location_data_simple["paris-r1"]
    paris_r2 = hierarchical_location_data_simple["paris-r2"]

    paris_r2_updated = await NodeManager.get_one(db=db, branch=default_branch, id=paris_r2.id)
    paris_r2_updated.get_attribute("status").value = "online"
    await paris_r2_updated.save(db=db)

    query = await NodeGetHierarchyQuery.init(
        db=db,
        direction=RelationshipHierarchyDirection.DESCENDANTS,
        node_id=site_paris.id,
        node_schema=site_schema,
        branch=default_branch,
    )
    await query.execute(db=db)

    descendant_ids = list(query.get_peer_ids())
    assert descendant_ids == sorted([paris_r1.id, paris_r2.id])
