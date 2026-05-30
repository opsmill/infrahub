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


async def test_NodeGetHierarchyQuery_order_by_multi_field_mixed_direction(
    db: InfrahubDatabase,
    hierarchical_location_data_simple: dict[str, Node],
    default_branch: Branch,
) -> None:
    location_generic = registry.schema.get(name="LocationGeneric", branch=default_branch, duplicate=False)
    location_generic.order_by = ["status__value__desc", "name__value"]

    site_schema = registry.schema.get_node_schema(name="LocationSite", branch=default_branch, duplicate=False)
    rack_schema = registry.schema.get_node_schema(name="LocationRack", branch=default_branch, duplicate=False)

    multi_region = await Node.init(db=db, branch=default_branch, schema="LocationRegion")
    await multi_region.new(db=db, name="multi-region")
    await multi_region.save(db=db)

    multi_site = await Node.init(db=db, branch=default_branch, schema="LocationSite")
    await multi_site.new(db=db, name="multi-site", parent=multi_region.id)
    await multi_site.save(db=db)

    specs = [
        ("multi-rack-alpha", "offline"),
        ("multi-rack-bravo", "online"),
        ("multi-rack-charlie", "offline"),
        ("multi-rack-delta", "online"),
    ]
    racks_by_name: dict[str, Node] = {}
    for rack_name, status_value in specs:
        rack = await Node.init(db=db, branch=default_branch, schema=rack_schema)
        await rack.new(db=db, name=rack_name, parent=multi_site.id, status=status_value)
        await rack.save(db=db)
        racks_by_name[rack_name] = rack

    query = await NodeGetHierarchyQuery.init(
        db=db,
        direction=RelationshipHierarchyDirection.DESCENDANTS,
        node_id=multi_site.id,
        node_schema=site_schema,
        branch=default_branch,
    )
    await query.execute(db=db)

    descendant_ids = list(query.get_peer_ids())
    assert descendant_ids == [
        racks_by_name["multi-rack-bravo"].id,
        racks_by_name["multi-rack-delta"].id,
        racks_by_name["multi-rack-alpha"].id,
        racks_by_name["multi-rack-charlie"].id,
    ]


@dataclass
class MixedDirectionWithMetadataCase:
    name: str
    order_by: list[str]
    expected_indices: list[int]


# Creation order: 0=alpha(status=offline), 1=bravo(status=online), 2=charlie(status=offline), 3=delta(status=online).
# created_at strictly increases with index.
MIXED_DIRECTION_WITH_METADATA_CASES_HIERARCHY = [
    MixedDirectionWithMetadataCase(
        name="status_desc_then_metadata_created_desc",
        order_by=["status__value__desc", "node_metadata__created_at__desc"],
        expected_indices=[3, 1, 2, 0],
    ),
    MixedDirectionWithMetadataCase(
        name="status_desc_then_metadata_created_asc",
        order_by=["status__value__desc", "node_metadata__created_at"],
        expected_indices=[1, 3, 0, 2],
    ),
    MixedDirectionWithMetadataCase(
        name="metadata_created_desc_then_status_asc",
        order_by=["node_metadata__created_at__desc", "status__value"],
        expected_indices=[3, 2, 1, 0],
    ),
    MixedDirectionWithMetadataCase(
        name="metadata_created_asc_then_name_desc",
        order_by=["node_metadata__created_at", "name__value__desc"],
        expected_indices=[0, 1, 2, 3],
    ),
]


async def test_NodeGetHierarchyQuery_order_by_multi_field_mixed_direction_with_metadata(
    db: InfrahubDatabase,
    hierarchical_location_data_simple: dict[str, Node],
    default_branch: Branch,
) -> None:
    location_generic = registry.schema.get(name="LocationGeneric", branch=default_branch, duplicate=False)
    site_schema = registry.schema.get_node_schema(name="LocationSite", branch=default_branch, duplicate=False)
    rack_schema = registry.schema.get_node_schema(name="LocationRack", branch=default_branch, duplicate=False)

    mfm_region = await Node.init(db=db, branch=default_branch, schema="LocationRegion")
    await mfm_region.new(db=db, name="mfm-region")
    await mfm_region.save(db=db)

    mfm_site = await Node.init(db=db, branch=default_branch, schema="LocationSite")
    await mfm_site.new(db=db, name="mfm-site", parent=mfm_region.id)
    await mfm_site.save(db=db)

    specs = [
        ("mfm-rack-alpha", "offline"),
        ("mfm-rack-bravo", "online"),
        ("mfm-rack-charlie", "offline"),
        ("mfm-rack-delta", "online"),
    ]
    racks: list[Node] = []
    for rack_name, status_value in specs:
        rack = await Node.init(db=db, branch=default_branch, schema=rack_schema)
        await rack.new(db=db, name=rack_name, parent=mfm_site.id, status=status_value)
        await rack.save(db=db)
        racks.append(rack)

    for case in MIXED_DIRECTION_WITH_METADATA_CASES_HIERARCHY:
        location_generic.order_by = case.order_by
        query = await NodeGetHierarchyQuery.init(
            db=db,
            direction=RelationshipHierarchyDirection.DESCENDANTS,
            node_id=mfm_site.id,
            node_schema=site_schema,
            branch=default_branch,
        )
        await query.execute(db=db)
        descendant_ids = list(query.get_peer_ids())
        assert descendant_ids == [racks[i].id for i in case.expected_indices], (
            f"order_by={case.order_by!r} produced wrong order"
        )
