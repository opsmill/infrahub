from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import HashableModelState, InfrahubKind, RelationshipCardinality
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.schema.relationship_schema import RelationshipSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from tests.db_snapshot import DbSnapshotter
from tests.helpers.edge_timestamps import assert_edge_timestamps


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
    node = new_schema.get(name="TestingCriticality", duplicate=False)

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

    new_schema.set(name="TestingCriticality", schema=node)
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
    snapshot_0 = await snapshotter.snapshot()

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
    snapshot_1 = await snapshotter.snapshot()
    assert_edge_timestamps(snapshot_0, snapshot_1, at_str)

    # 5. Load updated schema with new attribute, new relationship, and updated properties
    updated_schema = create_updated_schema(default_branch)
    at_2 = Timestamp()
    at_2_str = at_2.to_string()

    await load_updated_schema(db, default_branch, updated_schema, at_2)

    # 6. Verify all new/modified edges (since snapshot_1) use the 'at_2' timestamp
    snapshot_2 = await snapshotter.snapshot()
    assert_edge_timestamps(snapshot_1, snapshot_2, at_2_str)

    # 7. Delete an attribute and relationship from the schema
    at_3 = Timestamp()
    at_3_str = at_3.to_string()

    schema_with_deletes = update_schema_with_deletes(
        branch=default_branch,
        node_kind="TestingCriticality",
        attribute_name="priority",  # Delete the attribute we added in step 5
        relationship_name="secondary_tag",  # Delete the relationship we added in step 5
    )
    await load_updated_schema(db, default_branch, schema_with_deletes, at_3)

    # 8. Verify all new/modified edges (since snapshot_2) use the 'at_3' timestamp
    snapshot_3 = await snapshotter.snapshot()
    assert_edge_timestamps(snapshot_2, snapshot_3, at_3_str)
