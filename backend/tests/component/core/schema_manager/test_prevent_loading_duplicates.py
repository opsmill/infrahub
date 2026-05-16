import uuid

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.models import HashableModelDiff
from infrahub.core.schema import (
    AttributeSchema,
    GenericSchema,
    NodeSchema,
    RelationshipSchema,
    SchemaRoot,
    internal_schema,
)
from infrahub.core.schema.manager import SchemaManager
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase


async def test_load_schema_to_db_idempotent(db: InfrahubDatabase, default_branch: Branch) -> None:
    """Loading a schema twice with id-less items must not produce duplicate DB rows."""
    registry.schema = SchemaManager()
    registry.schema.register_schema(schema=SchemaRoot(**internal_schema), branch=default_branch.name)

    user_schema = SchemaRoot(
        nodes=[
            NodeSchema(
                name="Widget",
                namespace="Testing",
                attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
            )
        ]
    )
    schema_branch = registry.schema.register_schema(schema=user_schema, branch=default_branch.name)
    await registry.schema.load_schema_to_db(schema=schema_branch, db=db, branch=default_branch, at=Timestamp())

    # Build a fresh SchemaBranch from the same definition with no ids
    fresh_branch = SchemaBranch(cache=registry.schema._cache, name=default_branch.name)
    fresh_branch.load_schema(schema=user_schema)
    fresh_branch.process()
    await registry.schema.load_schema_to_db(schema=fresh_branch, db=db, branch=default_branch, at=Timestamp())

    node_schema = registry.schema.get(name="SchemaNode", branch=default_branch)
    results = await SchemaManager.query(
        schema=node_schema,
        db=db,
        branch=default_branch,
        filters={"namespace__value": "Testing", "name__value": "Widget"},
    )
    assert len(results) == 1


async def test_load_schema_to_db_overrides_input_id_with_existing_db_id(
    db: InfrahubDatabase, default_branch: Branch, register_internal_models_schema: SchemaBranch
) -> None:
    """``load_schema_to_db`` resolves existing rows by ``(namespace, name)`` and uses the DB's
    uuid regardless of any stale id carried on the input schema."""
    node = NodeSchema(
        name="OverrideGadget",
        namespace="Testing",
        attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
    )
    await registry.schema.create_node_in_db(node=node, db=db, branch=default_branch, at=Timestamp(), user_id="user-id")
    db_id = registry.schema.get(name="TestingOverrideGadget", branch=default_branch).id

    # Build a fresh SchemaBranch whose registered schema carries a fake id. ``load_schema_to_db``
    # should ignore the fake id, find the existing row by (namespace, name), and update it.
    fake_id = str(uuid.uuid4())
    stale_node = NodeSchema(
        id=fake_id,
        name="OverrideGadget",
        namespace="Testing",
        attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
    )
    fresh_branch = SchemaBranch(cache=registry.schema._cache, name=default_branch.name)
    fresh_branch.load_schema(schema=SchemaRoot(nodes=[stale_node]))
    fresh_branch.set(name=stale_node.kind, schema=stale_node)  # ensure the stale id sticks
    fresh_branch.process()
    await registry.schema.load_schema_to_db(
        schema=fresh_branch, db=db, branch=default_branch, limit=[stale_node.kind], at=Timestamp()
    )

    result = registry.schema.get(name="TestingOverrideGadget", branch=default_branch)
    assert result.id == db_id
    assert result.id != fake_id


async def test_load_schema_to_db_no_duplicate_children_when_registry_stale(
    db: InfrahubDatabase, default_branch: Branch
) -> None:
    """Loading a schema with id-less attributes and relationships when DB rows already exist must
    reuse existing child rows (no duplicate ``SchemaAttribute`` / ``SchemaRelationship``) by
    matching on the child's name."""
    registry.schema = SchemaManager()
    registry.schema.register_schema(schema=SchemaRoot(**internal_schema), branch=default_branch.name)

    user_schema = SchemaRoot(
        nodes=[
            NodeSchema(
                name="Owner",
                namespace="Testing",
                attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
            ),
            NodeSchema(
                name="Vehicle",
                namespace="Testing",
                attributes=[
                    AttributeSchema(name="name", kind="Text", unique=True),
                    AttributeSchema(name="size", kind="Number", optional=True),
                ],
                relationships=[
                    RelationshipSchema(name="primary_owner", peer="TestingOwner", optional=True, cardinality="one"),
                ],
            ),
        ]
    )
    schema_branch = registry.schema.register_schema(schema=user_schema, branch=default_branch.name)
    await registry.schema.load_schema_to_db(schema=schema_branch, db=db, branch=default_branch, at=Timestamp())

    # Build a fresh SchemaBranch from the same definition (no ids, no inherited state).
    # ``load_schema_to_db`` should match the existing ``SchemaAttribute`` and ``SchemaRelationship``
    # children by name rather than creating duplicates.
    fresh_branch = SchemaBranch(cache=registry.schema._cache, name=default_branch.name)
    fresh_branch.load_schema(schema=user_schema)
    fresh_branch.process()
    await registry.schema.load_schema_to_db(schema=fresh_branch, db=db, branch=default_branch, at=Timestamp())

    parent_id = registry.schema.get(name="TestingVehicle", branch=default_branch).id
    attribute_schema = registry.schema.get(name="SchemaAttribute", branch=default_branch)
    attr_rows = await SchemaManager.query(
        schema=attribute_schema, db=db, branch=default_branch, filters={"node__id": parent_id}
    )
    assert sorted(a.name.value for a in attr_rows) == ["name", "size"]

    relationship_schema = registry.schema.get(name="SchemaRelationship", branch=default_branch)
    rel_rows = await SchemaManager.query(
        schema=relationship_schema, db=db, branch=default_branch, filters={"node__id": parent_id}
    )
    assert sorted(r.name.value for r in rel_rows) == ["primary_owner"]


async def test_load_schema_to_db_rename_with_new_idless_child_reuses_db_row(
    db: InfrahubDatabase, default_branch: Branch, register_internal_models_schema: SchemaBranch
) -> None:
    """Renaming a parent while adding a field that already exists on the renamed schema must
    not insert a duplicate field.
    """
    # Create the original schema
    original = NodeSchema(
        name="OldKind",
        namespace="Renametest",
        attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
    )
    await registry.schema.create_node_in_db(
        node=original, db=db, branch=default_branch, at=Timestamp(), user_id="user-id"
    )
    after_create = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
    old_schema = after_create.get(name="RenametestOldKind", duplicate=True)
    assert isinstance(old_schema, NodeSchema)
    old_schema_id = old_schema.id
    name_attr_id = next(a.id for a in old_schema.attributes if a.name == "name")

    # Simulate another worker adding ``color`` to the schema on the database
    old_schema.attributes.append(AttributeSchema(name="color", kind="Text", optional=True))
    diff = HashableModelDiff(changed={"attributes": HashableModelDiff(added={"color": None})})
    await registry.schema.update_node_in_db_based_on_diff(
        db=db, node=old_schema, diff=diff, branch=default_branch, at=Timestamp(), user_id="other-worker"
    )

    # Build the renamed input schema: node kind changes (id preserved), ``name`` attr keeps its
    # id, the new ``color`` attribute is id-less (registry never saw it)
    renamed = NodeSchema(
        id=old_schema_id,
        name="NewKind",
        namespace="Renametest2",
        attributes=[
            AttributeSchema(id=name_attr_id, name="name", kind="Text", unique=True),
            AttributeSchema(name="color", kind="Text", optional=True),
        ],
    )
    fresh_branch = SchemaBranch(cache={}, name=default_branch.name)
    fresh_branch.load_schema(schema=SchemaRoot(nodes=[renamed]))
    fresh_branch.set(name=renamed.kind, schema=renamed)
    fresh_branch.process()
    await registry.schema.load_schema_to_db(
        schema=fresh_branch, db=db, branch=default_branch, limit=[renamed.kind], at=Timestamp()
    )

    # Verify: node schema was renamed (same uuid), and there is exactly one ``color`` SchemaAttribute
    # linked to it (the pre-existing row was reused)
    final = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
    renamed_schema = final.get(name="Renametest2NewKind", duplicate=False)
    assert renamed_schema.id == old_schema_id
    attribute_schema = registry.schema.get(name="SchemaAttribute", branch=default_branch)
    color_rows = await SchemaManager.query(
        schema=attribute_schema,
        db=db,
        branch=default_branch,
        filters={"node__id": old_schema_id, "name__value": "color"},
    )
    assert len(color_rows) == 1


async def test_load_schema_to_db_rejects_type_mismatch(
    db: InfrahubDatabase, default_branch: Branch, register_internal_models_schema: SchemaBranch
) -> None:
    """If a ``(namespace, name)`` exists on the DB as a SchemaNode but the input is a
    GenericSchema (or vice versa), the upsert pipeline raises rather than silently routing
    through the wrong type bucket."""
    await registry.schema.create_node_in_db(
        node=NodeSchema(name="TypeMismatch", namespace="Testing"),
        db=db,
        branch=default_branch,
        at=Timestamp(),
        user_id="user-id",
    )

    mismatched = GenericSchema(name="TypeMismatch", namespace="Testing")
    fresh_branch = SchemaBranch(cache=registry.schema._cache, name=default_branch.name)
    fresh_branch.load_schema(schema=SchemaRoot(generics=[mismatched]))
    fresh_branch.process()
    with pytest.raises(ValueError, match=r"type mismatch"):
        await registry.schema.load_schema_to_db(
            schema=fresh_branch,
            db=db,
            branch=default_branch,
            limit=[mismatched.kind],
            at=Timestamp(),
        )
