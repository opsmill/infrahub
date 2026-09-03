"""Merge a branch carrying every schema-migration type, then roll the merge back on the default branch.

Data is created on the default branch, a branch applies all migration types, the branch is merged into
the default (bringing the migrated structure and its metadata onto the default branch), and the merge is
then rolled back. The default branch must end byte-for-byte identical to its pre-merge state.

This test does not validate the precise per-node effect of each migration. It only asserts that the
merge changed the default branch and that the rollback fully undid it.
"""

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import (
    HashableModelState,
    RelationshipCardinality,
    RelationshipDirection,
    RelationshipKind,
    SchemaPathType,
)
from infrahub.core.diff.coordinator import DiffCoordinator
from infrahub.core.diff.merger.merger import DiffMerger
from infrahub.core.initialization import create_branch
from infrahub.core.migrations.schema.attribute_kind_update import AttributeKindUpdateMigration
from infrahub.core.migrations.schema.attribute_name_update import AttributeNameUpdateMigration
from infrahub.core.migrations.schema.node_attribute_add import NodeAttributeAddMigration
from infrahub.core.migrations.schema.node_attribute_remove import NodeAttributeRemoveMigration
from infrahub.core.migrations.schema.node_kind_update import NodeKindUpdateMigration
from infrahub.core.migrations.schema.node_relationship_remove import NodeRelationshipRemoveMigration
from infrahub.core.migrations.schema.node_remove import NodeRemoveMigration
from infrahub.core.migrations.shared import MigrationInput, SchemaMigration
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.core.schema.relationship_schema import RelationshipSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.database.validation import verify_graph
from infrahub.dependencies.registry import get_component_registry
from tests.helpers.schema import load_schema
from tests.helpers.vertex_metadata import branch_edge_fingerprint, branch_metadata_fingerprint

BRANCH_USER_ID = "branch_user"

ALL_MIGRATIONS_SCHEMA = SchemaRoot(
    version="1.0",
    nodes=[
        NodeSchema(
            name="Widget",
            namespace="Test",
            attributes=[
                AttributeSchema(name="name", kind="Text", unique=True),
                AttributeSchema(name="color", kind="Text", optional=True),  # renamed -> new_color
                AttributeSchema(name="weight", kind="Number", optional=True),  # removed
                AttributeSchema(name="notes", kind="Text", optional=True),  # kind changed Text -> TextArea
            ],
            relationships=[
                RelationshipSchema(
                    name="keeper",
                    peer="TestKeeper",
                    kind=RelationshipKind.ATTRIBUTE,
                    optional=True,
                    cardinality=RelationshipCardinality.ONE,
                    direction=RelationshipDirection.OUTBOUND,
                    identifier="widget__keeper",
                ),  # relationship removed
            ],
        ),
        NodeSchema(
            name="Keeper",
            namespace="Test",
            attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
            relationships=[
                RelationshipSchema(
                    name="widgets",
                    peer="TestWidget",
                    optional=True,
                    cardinality=RelationshipCardinality.MANY,
                    direction=RelationshipDirection.INBOUND,
                    identifier="widget__keeper",
                ),
            ],
        ),
        NodeSchema(  # node kind updated
            name="Morph",
            namespace="Test",
            attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
            relationships=[
                RelationshipSchema(
                    name="companion",
                    peer="TestKeeper",
                    kind=RelationshipKind.ATTRIBUTE,
                    optional=True,
                    cardinality=RelationshipCardinality.ONE,
                    identifier="morph__companion",
                ),
            ],
        ),
        NodeSchema(  # schema to be deleted
            name="Doomed",
            namespace="Test",
            attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
            relationships=[
                RelationshipSchema(
                    name="guard",
                    peer="TestKeeper",
                    kind=RelationshipKind.ATTRIBUTE,
                    optional=True,
                    cardinality=RelationshipCardinality.ONE,
                    identifier="doomed__guard",
                ),
            ],
        ),
    ],
)


async def _apply_all_migrations_on_branch(db: InfrahubDatabase, branch: Branch) -> None:
    """Apply every schema-migration type on ``branch`` in a single schema update, then run each migration."""
    schema = registry.schema.get_schema_branch(name=branch.name)

    # Capture the pre-change node schemas (the ``previous`` side of each migration).
    original_widget = schema.get(name="TestWidget", duplicate=True)
    original_morph = schema.get(name="TestMorph", duplicate=True)
    original_doomed = schema.get(name="TestDoomed", duplicate=True)

    # Make every schema change on the candidate branch schema, then process + persist once.
    widget = schema.get(name="TestWidget", duplicate=True)
    widget.attributes.append(AttributeSchema(name="extra", kind="Text", optional=True))  # attribute add
    widget.get_attribute(name="weight").state = HashableModelState.ABSENT  # attribute remove
    widget.get_attribute(name="color").name = "new_color"  # attribute rename (id preserved)
    widget.get_attribute(name="notes").kind = "TextArea"  # attribute kind update
    widget.get_relationship(name="keeper").state = HashableModelState.ABSENT  # relationship remove
    schema.set(name="TestWidget", schema=widget)

    keeper = schema.get(name="TestKeeper", duplicate=True)  # remove the other side of the shared identifier
    keeper.get_relationship(name="widgets").state = HashableModelState.ABSENT
    schema.set(name="TestKeeper", schema=keeper)

    morph = schema.get(name="TestMorph", duplicate=True)  # node kind update TestMorph -> Test2Morph
    schema.delete(name="TestMorph")
    morph.namespace = "Test2"
    schema.set(name="Test2Morph", schema=morph)

    schema.delete(name="TestDoomed")  # node remove

    schema.process()
    await registry.schema.update_schema_branch(
        db=db,
        branch=branch,
        schema=schema,
        limit=["TestWidget", "TestKeeper", "TestMorph", "Test2Morph", "TestDoomed"],
        update_db=True,
    )

    new_widget = schema.get(name="TestWidget")
    migration_input = MigrationInput(db=db, at=Timestamp(), user_id=BRANCH_USER_ID)
    migrations: list[SchemaMigration] = [
        NodeAttributeAddMigration(
            previous_node_schema=original_widget,
            new_node_schema=new_widget,
            schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestWidget", field_name="extra"),
        ),
        NodeAttributeRemoveMigration(
            previous_node_schema=original_widget,
            new_node_schema=new_widget,
            schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestWidget", field_name="weight"),
        ),
        AttributeNameUpdateMigration(
            previous_node_schema=original_widget,
            new_node_schema=new_widget,
            schema_path=SchemaPath(
                path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestWidget", field_name="new_color"
            ),
        ),
        AttributeKindUpdateMigration(
            previous_node_schema=original_widget,
            new_node_schema=new_widget,
            schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestWidget", field_name="notes"),
        ),
        NodeRelationshipRemoveMigration(
            previous_node_schema=original_widget,
            new_node_schema=new_widget,
            schema_path=SchemaPath(
                path_type=SchemaPathType.RELATIONSHIP, schema_kind="TestWidget", field_name="keeper"
            ),
        ),
        NodeKindUpdateMigration(
            previous_node_schema=original_morph,
            new_node_schema=schema.get(name="Test2Morph"),
            schema_path=SchemaPath(
                path_type=SchemaPathType.ATTRIBUTE, schema_kind="Test2Morph", field_name="namespace"
            ),
        ),
        NodeRemoveMigration(
            previous_node_schema=original_doomed,
            new_node_schema=None,
            schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind="TestDoomed"),
        ),
    ]
    for migration in migrations:
        result = await migration.execute(migration_input=migration_input, branch=branch)
        assert not result.errors, f"{migration.name} failed: {result.errors}"


async def test_merge_then_rollback_with_all_migrations(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch
) -> None:
    """Merging a branch that applied every migration type, then rolling it back, restores the default branch."""
    await load_schema(db=db, schema=ALL_MIGRATIONS_SCHEMA, update_db=True)

    # Data on the default branch: every kind gets an attribute value and a relationship.
    keeper = await Node.init(db=db, schema="TestKeeper")
    await keeper.new(db=db, name="k1")
    await keeper.save(db=db)
    widget = await Node.init(db=db, schema="TestWidget")
    await widget.new(db=db, name="w1", color="red", weight=5, notes="hello", keeper=keeper.id)
    await widget.save(db=db)
    morph = await Node.init(db=db, schema="TestMorph")
    await morph.new(db=db, name="m1", companion=keeper.id)
    await morph.save(db=db)
    doomed = await Node.init(db=db, schema="TestDoomed")
    await doomed.new(db=db, name="d1", guard=keeper.id)
    await doomed.save(db=db)

    pre_merge_edges = await branch_edge_fingerprint(db=db, branch_name=default_branch.name)
    pre_merge_metadata = await branch_metadata_fingerprint(db=db, branch_name=default_branch.name)

    # Apply every migration type on a branch.
    branch = await create_branch(branch_name="all-migrations", db=db)
    await _apply_all_migrations_on_branch(db=db, branch=branch)

    # Merge the branch into the default branch.
    merge_at = Timestamp()
    component_registry = get_component_registry()
    diff_coordinator = await component_registry.get_component(DiffCoordinator, db=db, branch=branch)
    await diff_coordinator.update_branch_diff(base_branch=default_branch, diff_branch=branch)
    diff_merger = await component_registry.get_component(DiffMerger, db=db, branch=branch)
    await diff_merger.merge_graph(at=merge_at)

    # The merge changed the default branch, so its edges and the vertex metadata must differ
    # from the pre-merge state.
    assert await branch_edge_fingerprint(db=db, branch_name=default_branch.name) != pre_merge_edges
    assert await branch_metadata_fingerprint(db=db, branch_name=default_branch.name) != pre_merge_metadata

    # Roll the merge back on the default branch.
    await diff_merger.rollback(merge_started_at=merge_at)

    await verify_graph(db=db)

    # The default branch is byte-for-byte identical to its pre-merge state: both the edges and the vertex
    # metadata (updated_at/by restored, previous_* snapshots cleared) match the pre-merge snapshots.
    assert await branch_edge_fingerprint(db=db, branch_name=default_branch.name) == pre_merge_edges
    assert await branch_metadata_fingerprint(db=db, branch_name=default_branch.name) == pre_merge_metadata
