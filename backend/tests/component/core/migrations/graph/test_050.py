from dataclasses import dataclass, field

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import BranchSupportType, MetadataOptions, RelationshipCardinality
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.graph.m050_backfill_vertex_metadata import Migration050
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase

AGNOSTIC_TAG_SCHEMA = NodeSchema(
    name="Tag",
    namespace="Test",
    branch=BranchSupportType.AGNOSTIC,
    attributes=[
        AttributeSchema(
            name="name",
            kind="Text",
            branch=BranchSupportType.AGNOSTIC,
        ),
    ],
    relationships=[
        RelationshipSchema(
            name="owner",
            peer="TestPerson",
            identifier="testtag__testperson",
            branch=BranchSupportType.AGNOSTIC,
            cardinality=RelationshipCardinality.ONE,
            optional=True,
        ),
    ],
)

# Inverse relationship for TestPerson to TestTag
PERSON_TAGS_RELATIONSHIP = RelationshipSchema(
    name="tags",
    peer="TestTag",
    identifier="testtag__testperson",
    cardinality=RelationshipCardinality.MANY,
    branch=BranchSupportType.AGNOSTIC,
    optional=True,
)


@dataclass
class TimeWindow:
    """Represents a time window for when an operation occurred."""

    before: Timestamp
    after: Timestamp

    def contains(self, ts: Timestamp) -> bool:
        """Check if a timestamp falls within this window."""
        return self.before <= ts <= self.after


@dataclass
class AttributeTimeWindows:
    """Time windows for an attribute's creation and last update."""

    created: TimeWindow
    updated: TimeWindow


@dataclass
class RelationshipTimeWindows:
    """Time windows for a relationship's creation and last update.

    A relationship is uniquely identified by:
    - source node (the node that owns the relationship)
    - relationship name (e.g., "owner", "driver")
    - peer ID (the ID of the related node)
    """

    rel_name: str
    peer_id: str
    created: TimeWindow
    updated: TimeWindow


@dataclass
class NodeTimeWindows:
    """Time windows for a node and its attributes and relationships."""

    node_id: str
    created: TimeWindow
    updated: TimeWindow
    attributes: dict[str, AttributeTimeWindows] = field(default_factory=dict)
    relationships: list[RelationshipTimeWindows] = field(default_factory=list)


async def _validate_node_metadata(
    db: InfrahubDatabase,
    branch: Branch,
    windows: NodeTimeWindows,
    branch_agnostic: bool = False,
) -> None:
    """Validate that a node, its attributes, and its relationships have correct metadata timestamps.

    Args:
        db: Database connection
        branch: Branch to query
        windows: Expected time windows for the node, its attributes, and its relationships
        branch_agnostic: Whether to query branch-agnostically
    """
    node = await NodeManager.get_one(
        db=db,
        id=windows.node_id,
        branch=branch,
        branch_agnostic=branch_agnostic,
        include_metadata=MetadataOptions.USER_TIMESTAMPS,
    )
    assert node is not None, f"Node {windows.node_id} should exist"

    node_created_at = node._get_created_at()
    node_updated_at = node._get_updated_at()
    assert node_created_at is not None, f"Node {windows.node_id} should have created_at"
    assert node_updated_at is not None, f"Node {windows.node_id} should have updated_at"
    assert windows.created.contains(node_created_at), (
        f"Node {windows.node_id} created_at {node_created_at} should be within {windows.created}"
    )

    # Validate attributes
    latest_attr_updated_at: Timestamp | None = None
    for attr_name, attr_windows in windows.attributes.items():
        attr = node.get_attribute(attr_name)
        attr_created_at = attr._get_created_at()
        attr_updated_at = attr._get_updated_at()
        assert attr_created_at is not None, f"{windows.node_id}.{attr_name} should have created_at"
        assert attr_updated_at is not None, f"{windows.node_id}.{attr_name} should have updated_at"
        assert attr_windows.created.contains(attr_created_at), (
            f"{windows.node_id}.{attr_name} created_at {attr_created_at} should be within {attr_windows.created}"
        )
        assert attr_windows.updated.contains(attr_updated_at), (
            f"{windows.node_id}.{attr_name} updated_at {attr_updated_at} should be within {attr_windows.updated}"
        )
        if latest_attr_updated_at is None or attr_updated_at > latest_attr_updated_at:
            latest_attr_updated_at = attr_updated_at

    # Validate relationships
    # Must use NodeManager.query_peers with include_metadata to get relationship timestamps
    node_schema = node.get_schema()
    for rel_windows in windows.relationships:
        rel_schema = node_schema.get_relationship(name=rel_windows.rel_name)
        rels = await NodeManager.query_peers(
            db=db,
            branch=branch,
            ids=[windows.node_id],
            source_kind=node.get_kind(),
            schema=rel_schema,
            filters={},
            include_metadata=MetadataOptions.USER_TIMESTAMPS,
        )
        # Find the relationship with the expected peer_id
        rel = next((r for r in rels if r.peer_id == rel_windows.peer_id), None)
        assert rel is not None, f"{windows.node_id}.{rel_windows.rel_name} -> {rel_windows.peer_id} should exist"
        rel_created_at = rel._get_created_at()
        rel_updated_at = rel._get_updated_at()
        assert rel_created_at is not None, (
            f"{windows.node_id}.{rel_windows.rel_name} -> {rel_windows.peer_id} should have created_at"
        )
        assert rel_updated_at is not None, (
            f"{windows.node_id}.{rel_windows.rel_name} -> {rel_windows.peer_id} should have updated_at"
        )
        assert rel_windows.created.contains(rel_created_at), (
            f"{windows.node_id}.{rel_windows.rel_name} -> {rel_windows.peer_id} "
            f"created_at {rel_created_at} should be within {rel_windows.created}"
        )
        assert rel_windows.updated.contains(rel_updated_at), (
            f"{windows.node_id}.{rel_windows.rel_name} -> {rel_windows.peer_id} "
            f"updated_at {rel_updated_at} should be within {rel_windows.updated}"
        )


async def _validate_user_branch_node_not_affected(db: InfrahubDatabase, node_id: str) -> None:
    """Validate that a node on a user branch was NOT affected by the migration."""
    query = """
    MATCH (n:Node {uuid: $uuid})-[e:IS_PART_OF]->(:Root)
    WHERE e.branch_level = 2
    RETURN n.created_at AS created_at, n.updated_at AS updated_at
    """
    results = await db.execute_query(query=query, params={"uuid": node_id})
    if results:
        assert results[0]["created_at"] is None, "User branch node should not have created_at set by migration"
        assert results[0]["updated_at"] is None, "User branch node should not have updated_at set by migration"


async def _validate_all_metadata(
    db: InfrahubDatabase,
    default_branch: Branch,
    person1_windows: NodeTimeWindows,
    car1_windows: NodeTimeWindows,
    tag1_windows: NodeTimeWindows,
    person2_id: str,
) -> None:
    """Run all metadata validations."""
    # Validate person1 (no updates after creation, but has relationships)
    await _validate_node_metadata(
        db=db,
        branch=default_branch,
        windows=person1_windows,
    )

    # Validate car1 (color was updated after creation, has relationships)
    await _validate_node_metadata(
        db=db,
        branch=default_branch,
        windows=car1_windows,
    )

    # Specifically verify car1's color attribute was updated after creation
    car1 = await NodeManager.get_one(
        db=db,
        id=car1_windows.node_id,
        branch=default_branch,
        include_metadata=MetadataOptions.USER_TIMESTAMPS,
    )
    assert car1 is not None
    color_attr = car1.get_attribute("color")
    color_created_at = color_attr._get_created_at()
    color_updated_at = color_attr._get_updated_at()
    assert color_created_at is not None
    assert color_updated_at is not None
    assert color_updated_at > color_created_at, "color updated_at should be > created_at since it was modified"

    # Validate tag1 (branch-agnostic node on global branch with relationship)
    await _validate_node_metadata(
        db=db,
        branch=default_branch,
        windows=tag1_windows,
        branch_agnostic=True,
    )

    # Validate user branch node was NOT affected
    await _validate_user_branch_node_not_affected(db=db, node_id=person2_id)


async def test_migration_050(db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch) -> None:
    """Test that migration 050 correctly backfills metadata properties.

    This test:
    1. Creates Nodes, Attributes, and Relationships on default, global, and user branches
    2. Records time windows for each creation/update operation
    3. Deletes all metadata properties via Cypher to simulate pre-migration state
    4. Runs the migration
    5. Validates metadata timestamps fall within the recorded time windows
    6. Validates user branch data is not affected
    7. Validates idempotency (running twice produces same results)
    """
    # Register the agnostic tag schema and add the inverse relationship to TestPerson
    updated_person_schema = registry.schema.get(name="TestPerson", branch=default_branch, duplicate=True)
    updated_person_schema.relationships.append(PERSON_TAGS_RELATIONSHIP)
    registry.schema.register_schema(
        schema=SchemaRoot(nodes=[AGNOSTIC_TAG_SCHEMA, updated_person_schema]), branch=default_branch.name
    )

    # -------------------------------------------------------------------------
    # Create person1 and record time windows
    # -------------------------------------------------------------------------
    time_before_person1 = Timestamp()
    person1 = await Node.init(db=db, schema="TestPerson")
    await person1.new(db=db, name="Alice", height=170)
    await person1.save(db=db)
    time_after_person1 = Timestamp()

    person1_windows = NodeTimeWindows(
        node_id=person1.id,
        created=TimeWindow(before=time_before_person1, after=time_after_person1),
        updated=TimeWindow(before=time_before_person1, after=time_after_person1),
        attributes={
            "name": AttributeTimeWindows(
                created=TimeWindow(before=time_before_person1, after=time_after_person1),
                updated=TimeWindow(before=time_before_person1, after=time_after_person1),
            ),
            "height": AttributeTimeWindows(
                created=TimeWindow(before=time_before_person1, after=time_after_person1),
                updated=TimeWindow(before=time_before_person1, after=time_after_person1),
            ),
        },
    )

    # -------------------------------------------------------------------------
    # Create car1 with relationship to person1
    # -------------------------------------------------------------------------
    time_before_car1 = Timestamp()
    car1 = await Node.init(db=db, schema="TestCar")
    await car1.new(db=db, name="Honda", color="red", owner=person1)
    await car1.save(db=db)
    time_after_car1 = Timestamp()

    # car1 adds a relationship to person1, so person1's updated_at should be updated
    person1_windows.updated = TimeWindow(before=time_before_car1, after=time_after_car1)
    # person1's "cars" relationship (inbound from car1) is created when car1 is created
    person1_windows.relationships.append(
        RelationshipTimeWindows(
            rel_name="cars",
            peer_id=car1.id,
            created=TimeWindow(before=time_before_car1, after=time_after_car1),
            updated=TimeWindow(before=time_before_car1, after=time_after_car1),
        )
    )
    car1_windows = NodeTimeWindows(
        node_id=car1.id,
        created=TimeWindow(before=time_before_car1, after=time_after_car1),
        updated=TimeWindow(before=time_before_car1, after=time_after_car1),
        attributes={
            "name": AttributeTimeWindows(
                created=TimeWindow(before=time_before_car1, after=time_after_car1),
                updated=TimeWindow(before=time_before_car1, after=time_after_car1),
            ),
            "color": AttributeTimeWindows(
                created=TimeWindow(before=time_before_car1, after=time_after_car1),
                updated=TimeWindow(before=time_before_car1, after=time_after_car1),
            ),
        },
        relationships=[
            RelationshipTimeWindows(
                rel_name="owner",
                peer_id=person1.id,
                created=TimeWindow(before=time_before_car1, after=time_after_car1),
                updated=TimeWindow(before=time_before_car1, after=time_after_car1),
            )
        ],
    )

    # -------------------------------------------------------------------------
    # Update car1's color attribute - this changes the updated time window
    # -------------------------------------------------------------------------
    time_before_car1_update = Timestamp()
    car1.get_attribute("color").value = "blue"
    await car1.save(db=db)
    time_after_car1_update = Timestamp()

    # Update the time windows for car1 and its color attribute
    car1_windows.updated = TimeWindow(before=time_before_car1_update, after=time_after_car1_update)
    car1_windows.attributes["color"].updated = TimeWindow(before=time_before_car1_update, after=time_after_car1_update)

    # -------------------------------------------------------------------------
    # Update the owner relationship's is_protected property
    # This tests that relationship updated_at can differ from created_at
    # -------------------------------------------------------------------------
    car1_fresh = await NodeManager.get_one(db=db, id=car1.id, branch=default_branch)
    owner_rel_manager = car1_fresh.get_relationship("owner")
    owner_rel = await owner_rel_manager.get(db=db)
    assert owner_rel is not None
    assert not isinstance(owner_rel, list)  # cardinality-one returns single Relationship
    owner_rel.is_protected = True
    time_before_rel_update = Timestamp()
    await car1_fresh.save(db=db)
    time_after_rel_update = Timestamp()

    # Update the time windows for car1's owner relationship and car1's updated_at
    car1_windows.updated = TimeWindow(before=time_before_rel_update, after=time_after_rel_update)
    car1_windows.relationships[0].updated = TimeWindow(before=time_before_rel_update, after=time_after_rel_update)
    # person1's cars relationship is also updated (it's the same Relationship vertex)
    person1_windows.relationships[0].updated = TimeWindow(before=time_before_rel_update, after=time_after_rel_update)
    # person1's updated_at is also updated since a relationship was modified
    person1_windows.updated = TimeWindow(before=time_before_rel_update, after=time_after_rel_update)

    # -------------------------------------------------------------------------
    # Create tag1 (branch-agnostic, on global branch) with relationship to person1
    # -------------------------------------------------------------------------
    time_before_tag1 = Timestamp()
    tag1 = await Node.init(db=db, schema=AGNOSTIC_TAG_SCHEMA)
    await tag1.new(db=db, name="important", owner=person1)
    await tag1.save(db=db)
    time_after_tag1 = Timestamp()

    tag1_windows = NodeTimeWindows(
        node_id=tag1.id,
        created=TimeWindow(before=time_before_tag1, after=time_after_tag1),
        updated=TimeWindow(before=time_before_tag1, after=time_after_tag1),
        attributes={
            "name": AttributeTimeWindows(
                created=TimeWindow(before=time_before_tag1, after=time_after_tag1),
                updated=TimeWindow(before=time_before_tag1, after=time_after_tag1),
            ),
        },
        relationships=[
            RelationshipTimeWindows(
                rel_name="owner",
                peer_id=person1.id,
                created=TimeWindow(before=time_before_tag1, after=time_after_tag1),
                updated=TimeWindow(before=time_before_tag1, after=time_after_tag1),
            ),
        ],
    )
    # Update time windows for person1: peer of tag.owner
    person1_windows.updated = TimeWindow(before=time_before_tag1, after=time_after_tag1)
    person1_windows.relationships.append(
        RelationshipTimeWindows(
            rel_name="tags",
            peer_id=tag1.id,
            created=TimeWindow(before=time_before_tag1, after=time_after_tag1),
            updated=TimeWindow(before=time_before_tag1, after=time_after_tag1),
        )
    )

    # -------------------------------------------------------------------------
    # Create user branch and data (should NOT be affected by migration)
    # -------------------------------------------------------------------------
    user_branch = await create_branch(db=db, branch_name="user_branch")

    person2 = await Node.init(db=db, schema="TestPerson", branch=user_branch)
    await person2.new(db=db, name="Bob", height=180)
    await person2.save(db=db)

    car1_branch = await NodeManager.get_one(db=db, branch=user_branch, id=car1.id)
    car1_branch.get_attribute("color").value = "green"
    await car1_branch.save(db=db)

    # -------------------------------------------------------------------------
    # Update tag1's owner relationship on the default branch
    # Since tag1 is branch-agnostic, this updates the global branch data
    # -------------------------------------------------------------------------
    tag1_fresh = await NodeManager.get_one(db=db, id=tag1.id, branch=default_branch, branch_agnostic=True)
    tag1_owner_rel_manager = tag1_fresh.get_relationship("owner")
    tag1_owner_rel = await tag1_owner_rel_manager.get(db=db)
    assert tag1_owner_rel is not None
    assert not isinstance(tag1_owner_rel, list)
    tag1_owner_rel.is_protected = True
    # No time window update b/c this relationship is updated again below
    await tag1_fresh.save(db=db)

    # -------------------------------------------------------------------------
    # Update tag1's owner relationship on the user branch
    # Since tag1 is branch-agnostic, this also updates the global branch data
    # and the final updated_at should reflect this later update
    # -------------------------------------------------------------------------
    tag1_user_branch = await NodeManager.get_one(db=db, id=tag1.id, branch=user_branch, branch_agnostic=True)
    tag1_owner_rel_manager_branch = tag1_user_branch.get_relationship("owner")
    tag1_owner_rel_branch = await tag1_owner_rel_manager_branch.get(db=db)
    assert tag1_owner_rel_branch is not None
    assert not isinstance(tag1_owner_rel_branch, list)
    tag1_owner_rel_branch.is_protected = False  # Toggle back to false
    time_before_tag1_rel_update_user = Timestamp()
    await tag1_user_branch.save(db=db)
    time_after_tag1_rel_update_user = Timestamp()

    # Update time windows for tag1's relationship and node updated_at to reflect user branch update
    tag1_windows.updated = TimeWindow(before=time_before_tag1_rel_update_user, after=time_after_tag1_rel_update_user)
    tag1_windows.relationships[0].updated = TimeWindow(
        before=time_before_tag1_rel_update_user, after=time_after_tag1_rel_update_user
    )
    # Update time windows for person1: peer of tag.owner
    person1_windows.updated = TimeWindow(before=time_before_tag1_rel_update_user, after=time_after_tag1_rel_update_user)
    person1_windows.relationships[1].updated = TimeWindow(
        before=time_before_tag1_rel_update_user, after=time_after_tag1_rel_update_user
    )

    # -------------------------------------------------------------------------
    # Delete all metadata properties to simulate pre-migration state
    # -------------------------------------------------------------------------
    delete_metadata_query = """
    CALL () {
        MATCH (n:Node)
        REMOVE n.created_at, n.created_by, n.updated_at, n.updated_by
    }
    CALL () {
        MATCH (attr:Attribute)
        REMOVE attr.created_at, attr.created_by, attr.updated_at, attr.updated_by
    }
    CALL () {
        MATCH (rel:Relationship)
        REMOVE rel.created_at, rel.created_by, rel.updated_at, rel.updated_by
    }
    """
    await db.execute_query(query=delete_metadata_query)

    # -------------------------------------------------------------------------
    # Run the migration first time
    # -------------------------------------------------------------------------
    migration = Migration050()
    execution_result = await migration.execute(migration_input=MigrationInput(db=db))
    assert not execution_result.errors, f"Migration execution failed: {execution_result.errors}"

    # -------------------------------------------------------------------------
    # Validate all metadata after first run
    # -------------------------------------------------------------------------
    await _validate_all_metadata(
        db=db,
        default_branch=default_branch,
        person1_windows=person1_windows,
        car1_windows=car1_windows,
        tag1_windows=tag1_windows,
        person2_id=person2.id,
    )

    # -------------------------------------------------------------------------
    # Run migration again (idempotency test)
    # -------------------------------------------------------------------------
    migration_again = Migration050()
    execution_result = await migration_again.execute(migration_input=MigrationInput(db=db))
    assert not execution_result.errors, f"Migration execution failed: {execution_result.errors}"

    # -------------------------------------------------------------------------
    # Validate all metadata after second run (should be identical)
    # -------------------------------------------------------------------------
    await _validate_all_metadata(
        db=db,
        default_branch=default_branch,
        person1_windows=person1_windows,
        car1_windows=car1_windows,
        tag1_windows=tag1_windows,
        person2_id=person2.id,
    )
