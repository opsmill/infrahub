from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import HashableModelState, InfrahubKind, RelationshipCardinality
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.schema.relationship_schema import RelationshipSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from tests.db_snapshot import DbEdge, DbSnapshot, DbSnapshotter


async def assert_edge_timestamps(
    db: InfrahubDatabase,
    before_edges_by_id: dict[str, DbEdge],
    expected_timestamp: str,
) -> DbSnapshot:
    """Take a snapshot and verify all new/modified edges use the expected timestamp.

    For new edges: 'from' must equal expected_timestamp
    For modified edges: changed 'to' must equal expected_timestamp
    """
    snapshotter = DbSnapshotter(db)
    after_snapshot = await snapshotter.snapshot()
    after_edges_by_id = {e.db_id: e for e in after_snapshot.edge_map.values()}

    for edge_id, after_edge in after_edges_by_id.items():
        before_edge = before_edges_by_id.get(edge_id)

        if before_edge is None:
            # New edge - 'from' must equal expected_timestamp
            from_time = after_edge.properties.get("from")
            assert from_time == expected_timestamp, (
                f"New edge {after_edge.edge_type} has from={from_time}, expected {expected_timestamp}"
            )
        else:
            # Check for modified 'to' time (from never changes once set)
            before_to = before_edge.properties.get("to")
            after_to = after_edge.properties.get("to")

            if before_to != after_to:
                assert after_to == expected_timestamp, (
                    f"Modified edge {after_edge.edge_type} has to={after_to}, expected {expected_timestamp}"
                )

    return after_snapshot


def create_updated_schema(branch: Branch) -> SchemaBranch:
    """Create an updated schema with various modifications.

    Modifications include:
    - A new attribute ("priority" on Criticality)
    - A new relationship ("secondary_tag" on Criticality)
    - An updated node property (Criticality label changed)
    - An attribute with an updated property ("description" label changed)
    - A relationship with an updated property ("tags" label changed)
    """
    current_schema = registry.schema.get_schema_branch(name=branch.name)
    new_schema = current_schema.duplicate()

    # Get a duplicate of the Criticality node to modify
    node = new_schema.get(name="BuiltinCriticality", duplicate=False)

    # Update node property
    node.label = "Updated Criticality"

    # Add new attribute
    node.attributes.append(AttributeSchema(name="priority", kind="Number", label="Priority", optional=True))

    # Update existing attribute property
    description_attr = node.get_attribute(name="description")
    description_attr.label = "Updated Description"

    # Add new relationship
    node.relationships.append(
        RelationshipSchema(
            name="secondary_tag",
            peer=InfrahubKind.TAG,
            label="Secondary Tag",
            identifier="secondary_tag__criticality",
            optional=True,
            cardinality=RelationshipCardinality.ONE,
        )
    )

    # Update existing relationship property
    tags_rel = node.get_relationship(name="tags")
    tags_rel.label = "Updated Tags"

    new_schema.set(name="BuiltinCriticality", schema=node)
    new_schema.process()

    return new_schema


async def load_updated_schema(
    db: InfrahubDatabase,
    branch: Branch,
    new_schema: SchemaBranch,
    at: Timestamp,
) -> None:
    """Load an updated schema using update_schema_branch with a diff."""
    current_schema = registry.schema.get_schema_branch(name=branch.name)

    # Compute the diff between current and new schema
    diff = current_schema.diff(other=new_schema)

    # Update the schema with the diff
    await registry.schema.update_schema_branch(
        schema=new_schema,
        db=db,
        branch=branch,
        diff=diff,
        at=at,
    )


def update_schema_with_deletes(
    branch: Branch,
    node_kind: str,
    attribute_name: str,
    relationship_name: str,
) -> SchemaBranch:
    """Create a schema with an attribute and relationship marked as ABSENT (deleted)."""
    current_schema = registry.schema.get_schema_branch(name=branch.name)
    new_schema = current_schema.duplicate()

    # Get the node and mark the attribute and relationship as absent
    node = new_schema.get(name=node_kind, duplicate=False)

    attr = node.get_attribute(name=attribute_name)
    attr.state = HashableModelState.ABSENT

    rel = node.get_relationship(name=relationship_name)
    rel.state = HashableModelState.ABSENT

    new_schema.set(name=node_kind, schema=node)

    return new_schema


async def test_schema_load_edges_use_at_timestamp(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    schema_criticality_tag: dict,
) -> None:
    """Verify that every edge updated during schema load uses the 'at' timestamp.

    When loading a schema via update_schema_branch(), all new edges should have
    their 'from' time set to the 'at' parameter, and all modified edges should
    have their 'to' time set to the 'at' parameter.
    """
    # 1. Snapshot before loading the schema
    snapshotter = DbSnapshotter(db)
    before_snapshot = await snapshotter.snapshot()
    before_edges_by_id = {e.db_id: e for e in before_snapshot.edge_map.values()}

    # 2. Create explicit timestamp for the 'at' parameter
    at = Timestamp()
    at_str = at.to_string()

    # 3. Load schema using update_schema_branch with the explicit 'at' parameter
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    schema_branch.load_schema(schema=SchemaRoot(**schema_criticality_tag))
    schema_branch.process()

    await registry.schema.update_schema_branch(
        schema=schema_branch,
        db=db,
        branch=default_branch,
        at=at,
    )

    # 4. Verify all new/modified edges use the 'at' timestamp
    snapshot_1 = await assert_edge_timestamps(db, before_edges_by_id, at_str)
    snapshot_1_edges_by_id = {e.db_id: e for e in snapshot_1.edge_map.values()}

    # 5. Load updated schema with new attribute, new relationship, and updated properties
    updated_schema = create_updated_schema(default_branch)
    at_2 = Timestamp()
    at_2_str = at_2.to_string()

    await load_updated_schema(db, default_branch, updated_schema, at_2)

    # 6. Verify all new/modified edges (since snapshot_1) use the 'at_2' timestamp
    snapshot_2 = await assert_edge_timestamps(db, snapshot_1_edges_by_id, at_2_str)
    snapshot_2_edges_by_id = {e.db_id: e for e in snapshot_2.edge_map.values()}

    # 7. Delete an attribute and relationship from the schema
    at_3 = Timestamp()
    at_3_str = at_3.to_string()

    schema_with_deletes = update_schema_with_deletes(
        branch=default_branch,
        node_kind="BuiltinCriticality",
        attribute_name="priority",  # Delete the attribute we added in step 5
        relationship_name="secondary_tag",  # Delete the relationship we added in step 5
    )
    await load_updated_schema(db, default_branch, schema_with_deletes, at_3)

    # 8. Verify all new/modified edges (since snapshot_2) use the 'at_3' timestamp
    await assert_edge_timestamps(db, snapshot_2_edges_by_id, at_3_str)
