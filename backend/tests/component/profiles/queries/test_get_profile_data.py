from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core.constants import RelationshipCardinality, RelationshipDirection
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.core.timestamp import Timestamp
from infrahub.database import DatabaseType
from infrahub.profiles.queries.get_profile_data import GetProfileDataQuery, ProfileData, RelationshipFilter
from tests.helpers.schema import load_schema

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

SITE = NodeSchema(name="Site", namespace="Test", attributes=[AttributeSchema(name="name", kind="Text", unique=True)])
RACK = NodeSchema(name="Rack", namespace="Test", attributes=[AttributeSchema(name="name", kind="Text", unique=True)])
LABEL = NodeSchema(name="Label", namespace="Test", attributes=[AttributeSchema(name="name", kind="Text", unique=True)])
DEVICE = NodeSchema(
    name="Device",
    namespace="Test",
    attributes=[
        AttributeSchema(name="name", kind="Text", unique=True),
        AttributeSchema(name="description", kind="Text", optional=True),
        AttributeSchema(name="status", kind="Text", optional=True),
    ],
    relationships=[
        RelationshipSchema(
            name="site",
            peer="TestSite",
            identifier="device__site",
            cardinality=RelationshipCardinality.ONE,
            optional=True,
        ),
        RelationshipSchema(
            name="rack",
            peer="TestRack",
            identifier="device__rack",
            cardinality=RelationshipCardinality.ONE,
            direction=RelationshipDirection.OUTBOUND,
            optional=True,
        ),
        RelationshipSchema(
            name="labels",
            peer="TestLabel",
            identifier="device__label",
            cardinality=RelationshipCardinality.MANY,
            direction=RelationshipDirection.INBOUND,
            optional=True,
        ),
    ],
)

SITE_FILTER = RelationshipFilter(relationship_identifier="profile_device__site", direction=RelationshipDirection.BIDIR)
RACK_FILTER = RelationshipFilter(
    relationship_identifier="profile_device__rack", direction=RelationshipDirection.OUTBOUND
)
LABELS_FILTER = RelationshipFilter(
    relationship_identifier="profile_device__label", direction=RelationshipDirection.INBOUND
)
ALL_FILTERS = [SITE_FILTER, RACK_FILTER, LABELS_FILTER]


@dataclass(frozen=True)
class Peers:
    sites: list[Node]
    racks: list[Node]
    labels: list[Node]


async def _create_node(db: InfrahubDatabase, branch: Branch, kind: str, **data: Any) -> Node:
    node = await Node.init(db=db, schema=kind, branch=branch)
    await node.new(db=db, **data)
    await node.save(db=db)
    return node


@pytest.fixture
async def peers(db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: None) -> Peers:
    await load_schema(db=db, schema=SchemaRoot(nodes=[SITE, RACK, LABEL, DEVICE]), branch_name=default_branch.name)
    return Peers(
        sites=[
            await _create_node(db=db, branch=default_branch, kind="TestSite", name=f"site-{idx}") for idx in range(2)
        ],
        racks=[
            await _create_node(db=db, branch=default_branch, kind="TestRack", name=f"rack-{idx}") for idx in range(2)
        ],
        labels=[
            await _create_node(db=db, branch=default_branch, kind="TestLabel", name=f"label-{idx}") for idx in range(3)
        ],
    )


async def _get_profile_data(
    db: InfrahubDatabase,
    branch: Branch,
    profile_ids: list[str],
    attr_names: list[str],
    relationship_filters: list[RelationshipFilter] | None = None,
    at: Timestamp | None = None,
) -> list[ProfileData]:
    """Return the results sorted by profile, with sorted peers, because the query collects them in no order."""
    query = await GetProfileDataQuery.init(
        db=db,
        branch=branch,
        at=at,
        profile_ids=profile_ids,
        attr_names=attr_names,
        relationship_filters=relationship_filters,
    )
    await query.execute(db=db)
    profile_data_list = sorted(query.get_profile_data(), key=lambda profile_data: profile_data.uuid)
    for profile_data in profile_data_list:
        profile_data.relationship_peers = {
            rel_filter: sorted(peer_ids) for rel_filter, peer_ids in profile_data.relationship_peers.items()
        }
    return profile_data_list


def _ids(*nodes: Node) -> list[str]:
    return sorted(node.id for node in nodes)


async def test_reads_requested_attributes_and_priority(
    db: InfrahubDatabase, default_branch: Branch, peers: Peers
) -> None:
    profile = await _create_node(
        db=db,
        branch=default_branch,
        kind="ProfileTestDevice",
        profile_name="profile-1",
        profile_priority=10,
        description="from-profile",
    )

    result = await _get_profile_data(
        db=db, branch=default_branch, profile_ids=[profile.id], attr_names=["description", "status"]
    )

    assert result == [
        ProfileData(
            uuid=profile.id,
            priority=10,
            attribute_values={"description": "from-profile", "status": None},
            relationship_peers={},
        )
    ]


async def test_reads_priority_without_requested_attributes(
    db: InfrahubDatabase, default_branch: Branch, peers: Peers
) -> None:
    profile = await _create_node(
        db=db,
        branch=default_branch,
        kind="ProfileTestDevice",
        profile_name="profile-1",
        profile_priority=10,
        description="from-profile",
    )

    result = await _get_profile_data(db=db, branch=default_branch, profile_ids=[profile.id], attr_names=[])

    assert result == [ProfileData(uuid=profile.id, priority=10, attribute_values={}, relationship_peers={})]


async def test_ignores_relationships_without_filters(
    db: InfrahubDatabase, default_branch: Branch, peers: Peers
) -> None:
    profile = await _create_node(
        db=db,
        branch=default_branch,
        kind="ProfileTestDevice",
        profile_name="profile-1",
        profile_priority=10,
        site=peers.sites[0],
        rack=peers.racks[0],
        labels=peers.labels[:2],
    )
    await _create_node(db=db, branch=default_branch, kind="TestDevice", name="device-0", profiles=[profile])

    result = await _get_profile_data(db=db, branch=default_branch, profile_ids=[profile.id], attr_names=["status"])

    assert result == [
        ProfileData(uuid=profile.id, priority=10, attribute_values={"status": None}, relationship_peers={})
    ]


async def test_reads_relationship_peers_in_each_direction(
    db: InfrahubDatabase, default_branch: Branch, peers: Peers
) -> None:
    profile = await _create_node(
        db=db,
        branch=default_branch,
        kind="ProfileTestDevice",
        profile_name="profile-1",
        profile_priority=10,
        site=peers.sites[0],
        rack=peers.racks[0],
        labels=peers.labels[:2],
    )
    for idx in range(2):
        await _create_node(db=db, branch=default_branch, kind="TestDevice", name=f"device-{idx}", profiles=[profile])

    result = await _get_profile_data(
        db=db, branch=default_branch, profile_ids=[profile.id], attr_names=[], relationship_filters=ALL_FILTERS
    )

    assert result == [
        ProfileData(
            uuid=profile.id,
            priority=10,
            attribute_values={},
            relationship_peers={
                SITE_FILTER: _ids(peers.sites[0]),
                RACK_FILTER: _ids(peers.racks[0]),
                LABELS_FILTER: _ids(*peers.labels[:2]),
            },
        )
    ]


async def test_reads_only_the_filtered_relationships(
    db: InfrahubDatabase, default_branch: Branch, peers: Peers
) -> None:
    profile = await _create_node(
        db=db,
        branch=default_branch,
        kind="ProfileTestDevice",
        profile_name="profile-1",
        profile_priority=10,
        site=peers.sites[0],
        rack=peers.racks[0],
        labels=peers.labels[:2],
    )

    result = await _get_profile_data(
        db=db, branch=default_branch, profile_ids=[profile.id], attr_names=[], relationship_filters=[RACK_FILTER]
    )

    assert result == [
        ProfileData(
            uuid=profile.id, priority=10, attribute_values={}, relationship_peers={RACK_FILTER: _ids(peers.racks[0])}
        )
    ]


async def test_skips_filters_whose_direction_does_not_match(
    db: InfrahubDatabase, default_branch: Branch, peers: Peers
) -> None:
    profile = await _create_node(
        db=db,
        branch=default_branch,
        kind="ProfileTestDevice",
        profile_name="profile-1",
        profile_priority=10,
        site=peers.sites[0],
        rack=peers.racks[0],
        labels=peers.labels[:2],
    )
    mismatched_filters = [
        RelationshipFilter(relationship_identifier="profile_device__site", direction=RelationshipDirection.OUTBOUND),
        RelationshipFilter(relationship_identifier="profile_device__rack", direction=RelationshipDirection.INBOUND),
        RelationshipFilter(relationship_identifier="profile_device__label", direction=RelationshipDirection.BIDIR),
    ]

    result = await _get_profile_data(
        db=db, branch=default_branch, profile_ids=[profile.id], attr_names=[], relationship_filters=mismatched_filters
    )

    assert result == [ProfileData(uuid=profile.id, priority=10, attribute_values={}, relationship_peers={})]


async def test_reads_each_profile_separately(db: InfrahubDatabase, default_branch: Branch, peers: Peers) -> None:
    first = await _create_node(
        db=db,
        branch=default_branch,
        kind="ProfileTestDevice",
        profile_name="first",
        profile_priority=10,
        description="first",
        site=peers.sites[0],
        labels=[peers.labels[0]],
    )
    second = await _create_node(
        db=db,
        branch=default_branch,
        kind="ProfileTestDevice",
        profile_name="second",
        profile_priority=20,
        description="second",
        site=peers.sites[1],
        rack=peers.racks[0],
        labels=peers.labels[1:],
    )
    await _create_node(
        db=db,
        branch=default_branch,
        kind="ProfileTestDevice",
        profile_name="not-requested",
        profile_priority=30,
        description="not-requested",
        site=peers.sites[0],
        rack=peers.racks[1],
        labels=peers.labels,
    )

    result = await _get_profile_data(
        db=db,
        branch=default_branch,
        profile_ids=[first.id, second.id],
        attr_names=["description"],
        relationship_filters=ALL_FILTERS,
    )

    assert {profile_data.uuid: profile_data for profile_data in result} == {
        first.id: ProfileData(
            uuid=first.id,
            priority=10,
            attribute_values={"description": "first"},
            relationship_peers={SITE_FILTER: _ids(peers.sites[0]), LABELS_FILTER: _ids(peers.labels[0])},
        ),
        second.id: ProfileData(
            uuid=second.id,
            priority=20,
            attribute_values={"description": "second"},
            relationship_peers={
                SITE_FILTER: _ids(peers.sites[1]),
                RACK_FILTER: _ids(peers.racks[0]),
                LABELS_FILTER: _ids(*peers.labels[1:]),
            },
        ),
    }


async def test_excludes_deleted_profiles(db: InfrahubDatabase, default_branch: Branch, peers: Peers) -> None:
    kept = await _create_node(
        db=db,
        branch=default_branch,
        kind="ProfileTestDevice",
        profile_name="kept",
        profile_priority=10,
        site=peers.sites[0],
    )
    deleted = await _create_node(
        db=db,
        branch=default_branch,
        kind="ProfileTestDevice",
        profile_name="deleted",
        profile_priority=20,
        site=peers.sites[1],
    )
    await deleted.delete(db=db)

    result = await _get_profile_data(
        db=db,
        branch=default_branch,
        profile_ids=[kept.id, deleted.id],
        attr_names=["description"],
        relationship_filters=ALL_FILTERS,
    )

    assert result == [
        ProfileData(
            uuid=kept.id,
            priority=10,
            attribute_values={"description": None},
            relationship_peers={SITE_FILTER: _ids(peers.sites[0])},
        )
    ]


async def test_excludes_profile_deleted_on_branch(db: InfrahubDatabase, default_branch: Branch, peers: Peers) -> None:
    profile = await _create_node(
        db=db,
        branch=default_branch,
        kind="ProfileTestDevice",
        profile_name="profile-1",
        profile_priority=10,
        site=peers.sites[0],
    )
    branch = await create_branch(branch_name="branch2", db=db)
    profile_on_branch = await NodeManager.get_one(db=db, branch=branch, id=profile.id, raise_on_error=True)
    await profile_on_branch.delete(db=db)

    on_branch = await _get_profile_data(
        db=db, branch=branch, profile_ids=[profile.id], attr_names=["description"], relationship_filters=ALL_FILTERS
    )
    on_main = await _get_profile_data(
        db=db,
        branch=default_branch,
        profile_ids=[profile.id],
        attr_names=["description"],
        relationship_filters=ALL_FILTERS,
    )

    assert on_branch == []
    assert on_main == [
        ProfileData(
            uuid=profile.id,
            priority=10,
            attribute_values={"description": None},
            relationship_peers={SITE_FILTER: _ids(peers.sites[0])},
        )
    ]


async def test_reads_values_of_the_requested_branch(db: InfrahubDatabase, default_branch: Branch, peers: Peers) -> None:
    profile = await _create_node(
        db=db,
        branch=default_branch,
        kind="ProfileTestDevice",
        profile_name="profile-1",
        profile_priority=10,
        description="on-main",
        site=peers.sites[0],
        rack=peers.racks[0],
        labels=peers.labels[:2],
    )
    branch = await create_branch(branch_name="branch2", db=db)
    profile_on_branch = await NodeManager.get_one(db=db, branch=branch, id=profile.id, raise_on_error=True)
    profile_on_branch.description.value = "on-branch"
    await profile_on_branch.site.update(db=db, data=peers.sites[1])
    await profile_on_branch.rack.update(db=db, data=None)
    await profile_on_branch.labels.update(db=db, data=peers.labels[1:])
    await profile_on_branch.save(db=db)

    on_branch = await _get_profile_data(
        db=db, branch=branch, profile_ids=[profile.id], attr_names=["description"], relationship_filters=ALL_FILTERS
    )
    on_main = await _get_profile_data(
        db=db,
        branch=default_branch,
        profile_ids=[profile.id],
        attr_names=["description"],
        relationship_filters=ALL_FILTERS,
    )

    assert on_branch == [
        ProfileData(
            uuid=profile.id,
            priority=10,
            attribute_values={"description": "on-branch"},
            relationship_peers={SITE_FILTER: _ids(peers.sites[1]), LABELS_FILTER: _ids(*peers.labels[1:])},
        )
    ]
    assert on_main == [
        ProfileData(
            uuid=profile.id,
            priority=10,
            attribute_values={"description": "on-main"},
            relationship_peers={
                SITE_FILTER: _ids(peers.sites[0]),
                RACK_FILTER: _ids(peers.racks[0]),
                LABELS_FILTER: _ids(*peers.labels[:2]),
            },
        )
    ]


async def test_reads_values_at_the_requested_time(db: InfrahubDatabase, default_branch: Branch, peers: Peers) -> None:
    profile = await _create_node(
        db=db,
        branch=default_branch,
        kind="ProfileTestDevice",
        profile_name="profile-1",
        profile_priority=10,
        description="before",
        site=peers.sites[0],
        labels=peers.labels[:2],
    )
    before_update = Timestamp()
    profile = await NodeManager.get_one(db=db, branch=default_branch, id=profile.id, raise_on_error=True)
    profile.description.value = "after"
    await profile.site.update(db=db, data=peers.sites[1])
    await profile.labels.update(db=db, data=[peers.labels[1]])
    await profile.save(db=db)

    current = await _get_profile_data(
        db=db,
        branch=default_branch,
        profile_ids=[profile.id],
        attr_names=["description"],
        relationship_filters=ALL_FILTERS,
    )
    previous = await _get_profile_data(
        db=db,
        branch=default_branch,
        profile_ids=[profile.id],
        attr_names=["description"],
        relationship_filters=ALL_FILTERS,
        at=before_update,
    )

    assert current == [
        ProfileData(
            uuid=profile.id,
            priority=10,
            attribute_values={"description": "after"},
            relationship_peers={SITE_FILTER: _ids(peers.sites[1]), LABELS_FILTER: _ids(peers.labels[1])},
        )
    ]
    assert previous == [
        ProfileData(
            uuid=profile.id,
            priority=10,
            attribute_values={"description": "before"},
            relationship_peers={SITE_FILTER: _ids(peers.sites[0]), LABELS_FILTER: _ids(*peers.labels[:2])},
        )
    ]


def _sum_db_hits(operator: dict[str, Any]) -> int:
    return operator["dbHits"] + sum(_sum_db_hits(operator=child) for child in operator.get("children", []))


async def _count_db_hits(
    db: InfrahubDatabase, branch: Branch, profile_id: str, relationship_filters: list[RelationshipFilter]
) -> int:
    query = await GetProfileDataQuery.init(
        db=db,
        branch=branch,
        profile_ids=[profile_id],
        attr_names=["description", "status"],
        relationship_filters=relationship_filters,
    )
    rendered = query.render()
    # Plan again with the current statistics: an old plan from a smaller database can scan full relationship indexes.
    await db.execute_query(query="CALL db.prepareForReplanning()")
    _, metadata = await db.execute_query_with_metadata(
        query=f"PROFILE\n{rendered.text}", params=rendered.params, name=query.name, type=query.type
    )
    return _sum_db_hits(operator=metadata["profile"])


async def _create_linked_profile(
    db: InfrahubDatabase, branch: Branch, peers: Peers, name: str, linked_nodes: int
) -> Node:
    profile = await _create_node(
        db=db,
        branch=branch,
        kind="ProfileTestDevice",
        profile_name=name,
        profile_priority=10,
        description=name,
        site=peers.sites[0],
        rack=peers.racks[0],
        labels=peers.labels[:2],
    )
    for idx in range(linked_nodes):
        await _create_node(db=db, branch=branch, kind="TestDevice", name=f"{name}-device-{idx}", profiles=[profile])
    return profile


@pytest.mark.parametrize(
    "relationship_filters",
    [pytest.param([], id="attributes-only"), pytest.param(ALL_FILTERS, id="with-relationship-filters")],
)
async def test_db_hits_do_not_grow_with_linked_nodes(
    db: InfrahubDatabase, default_branch: Branch, peers: Peers, relationship_filters: list[RelationshipFilter]
) -> None:
    if db.db_type != DatabaseType.NEO4J:
        pytest.skip("PROFILE and db.prepareForReplanning() exist only in Neo4j")

    few = await _create_linked_profile(db=db, branch=default_branch, peers=peers, name="few", linked_nodes=2)
    many = await _create_linked_profile(db=db, branch=default_branch, peers=peers, name="many", linked_nodes=10)
    many = await NodeManager.get_one(db=db, branch=default_branch, id=many.id, raise_on_error=True)
    assert len(await many.related_nodes.get_relationships(db=db)) == 10

    few_hits = await _count_db_hits(
        db=db, branch=default_branch, profile_id=few.id, relationship_filters=relationship_filters
    )
    many_hits = await _count_db_hits(
        db=db, branch=default_branch, profile_id=many.id, relationship_filters=relationship_filters
    )

    assert many_hits == few_hits
