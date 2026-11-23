"""A schema, a data set and helpers to check that a schema migration counts exactly the nodes it changes.

The data set mixes active nodes, deleted nodes, nodes that exist only on a branch, profile and template
nodes, and branch-agnostic nodes, attributes and relationships, so that a selection that misses an
active-state check counts a different number of nodes than the write changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub.core import registry
from infrahub.core.constants import (
    BranchSupportType,
    RelationshipCardinality,
    RelationshipKind,
    SchemaPathType,
)
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.schema.attribute_kind_update import AttributeKindUpdateMigration
from infrahub.core.migrations.schema.attribute_name_update import AttributeNameUpdateMigration
from infrahub.core.migrations.schema.attribute_supports_generated_schema import (
    AttributeSupportsGeneratedSchemaMigration,
)
from infrahub.core.migrations.schema.node_attribute_add import NodeAttributeAddMigration
from infrahub.core.migrations.schema.node_attribute_remove import NodeAttributeRemoveMigration
from infrahub.core.migrations.schema.node_kind_update import NodeKindUpdateMigration
from infrahub.core.migrations.schema.node_relationship_remove import (
    NodeRelationshipRemoveMigration,
    RelationshipRemoveQueryParams,
)
from infrahub.core.migrations.schema.node_remove import NodeRemoveMigration
from infrahub.core.migrations.schema.tasks import get_derived_schema_pairs
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.core.schema.definitions.core.template import core_object_template
from infrahub.core.timestamp import Timestamp

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.migrations.query.selection import MigrationSelectionQuery
    from infrahub.core.migrations.shared import AttributeSchemaMigration
    from infrahub.database import InfrahubDatabase

SELECTION_BRANCH_NAME = "sel-branch"

AttributeMigrationClass = type[
    NodeAttributeRemoveMigration
    | NodeAttributeAddMigration
    | AttributeNameUpdateMigration
    | AttributeKindUpdateMigration
    | AttributeSupportsGeneratedSchemaMigration
]

WIDGET_KIND = "SelWidget"
GADGET_KIND = "SelGadget"
BEACON_KIND = "SelBeacon"
EMPTY_KIND = "SelEmpty"

GADGET_IDENTIFIER = "sel_widget__sel_gadget"
PARTNER_IDENTIFIER = "sel_widget_partner__sel_gadget"

SEL_WIDGET = NodeSchema(
    name="Widget",
    namespace="Sel",
    branch=BranchSupportType.AWARE,
    generate_profile=True,
    generate_template=True,
    attributes=[
        AttributeSchema(name="name", kind="Text", unique=True),
        AttributeSchema(name="color", kind="Text", optional=True),
        AttributeSchema(name="serial", kind="Number", optional=True, branch=BranchSupportType.AGNOSTIC),
    ],
    relationships=[
        RelationshipSchema(
            name="gadget",
            kind=RelationshipKind.GENERIC,
            peer=GADGET_KIND,
            identifier=GADGET_IDENTIFIER,
            cardinality=RelationshipCardinality.ONE,
            optional=True,
            branch=BranchSupportType.AWARE,
        ),
        RelationshipSchema(
            name="partner",
            kind=RelationshipKind.GENERIC,
            peer=GADGET_KIND,
            identifier=PARTNER_IDENTIFIER,
            cardinality=RelationshipCardinality.ONE,
            optional=True,
            branch=BranchSupportType.AGNOSTIC,
        ),
    ],
)

SEL_GADGET = NodeSchema(
    name="Gadget",
    namespace="Sel",
    branch=BranchSupportType.AWARE,
    attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
    relationships=[
        RelationshipSchema(
            name="widgets",
            kind=RelationshipKind.GENERIC,
            peer=WIDGET_KIND,
            identifier=GADGET_IDENTIFIER,
            cardinality=RelationshipCardinality.MANY,
            optional=True,
            branch=BranchSupportType.AWARE,
        ),
        RelationshipSchema(
            name="partners",
            kind=RelationshipKind.GENERIC,
            peer=WIDGET_KIND,
            identifier=PARTNER_IDENTIFIER,
            cardinality=RelationshipCardinality.MANY,
            optional=True,
            branch=BranchSupportType.AGNOSTIC,
        ),
    ],
)

SEL_BEACON = NodeSchema(
    name="Beacon",
    namespace="Sel",
    branch=BranchSupportType.AGNOSTIC,
    attributes=[
        AttributeSchema(name="name", kind="Text", unique=True),
        AttributeSchema(name="serial", kind="Number", optional=True),
    ],
)

SEL_EMPTY = NodeSchema(
    name="Empty",
    namespace="Sel",
    branch=BranchSupportType.AWARE,
    attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
)

SELECTION_SCHEMA = SchemaRoot(nodes=[SEL_WIDGET, SEL_GADGET, SEL_BEACON, SEL_EMPTY])


@dataclass
class SelectionDataset:
    branch: Branch
    nodes: dict[str, Node]


def load_selection_schema(default_branch: Branch) -> None:
    registry.schema.register_schema(schema=SchemaRoot(generics=[core_object_template]), branch=default_branch.name)
    registry.schema.register_schema(schema=SELECTION_SCHEMA.duplicate(), branch=default_branch.name)


async def _create(db: InfrahubDatabase, branch: Branch, kind: str, **values: Any) -> Node:
    node = await Node.init(db=db, schema=kind, branch=branch)
    await node.new(db=db, **values)
    await node.save(db=db)
    return node


async def _delete(db: InfrahubDatabase, branch: Branch, node_id: str) -> None:
    node = await NodeManager.get_one(db=db, id=node_id, branch=branch, raise_on_error=True)
    await node.delete(db=db)


async def load_selection_dataset(db: InfrahubDatabase, default_branch: Branch) -> SelectionDataset:
    load_selection_schema(default_branch=default_branch)
    main = default_branch
    nodes: dict[str, Node] = {}

    nodes["g1"] = await _create(db, main, GADGET_KIND, name="g1")
    nodes["g2"] = await _create(db, main, GADGET_KIND, name="g2")
    nodes["w1"] = await _create(
        db, main, WIDGET_KIND, name="w1", color="red", serial=1, gadget=nodes["g1"], partner=nodes["g1"]
    )
    nodes["w2"] = await _create(db, main, WIDGET_KIND, name="w2", color="blue", serial=2, gadget=nodes["g1"])
    nodes["w3"] = await _create(db, main, WIDGET_KIND, name="w3")
    nodes["w4"] = await _create(db, main, WIDGET_KIND, name="w4", color="gray")
    await _delete(db, main, nodes["w4"].id)
    nodes["pw1"] = await _create(db, main, f"Profile{WIDGET_KIND}", profile_name="pw1", color="black")
    nodes["tw1"] = await _create(db, main, f"Template{WIDGET_KIND}", template_name="tw1")
    nodes["b1"] = await _create(db, main, BEACON_KIND, name="b1", serial=5)
    nodes["b2"] = await _create(db, main, BEACON_KIND, name="b2")
    nodes["b3"] = await _create(db, main, BEACON_KIND, name="b3")
    await _delete(db, main, nodes["b3"].id)

    branch = await create_branch(db=db, branch_name=SELECTION_BRANCH_NAME)
    nodes["w5"] = await _create(db, branch, WIDGET_KIND, name="w5", color="green", gadget=nodes["g2"])
    nodes["w6"] = await _create(db, branch, WIDGET_KIND, name="w6", gadget=nodes["g2"])
    await _delete(db, branch, nodes["w2"].id)
    w1_on_branch = await NodeManager.get_one(db=db, id=nodes["w1"].id, branch=branch, raise_on_error=True)
    w1_on_branch.get_attribute(name="color").value = "orange"
    await w1_on_branch.save(db=db)

    return SelectionDataset(branch=branch, nodes=nodes)


def population(kind: str) -> list[str]:
    """Return the kinds whose nodes a migration of `kind` may change: the kind and its profile and template kinds."""
    return [kind, f"Profile{kind}", f"Template{kind}"]


def get_branch(dataset: SelectionDataset, default_branch: Branch, branch_name: str) -> Branch:
    return dataset.branch if branch_name == SELECTION_BRANCH_NAME else default_branch


# ---------------------------------------------------------------------------
# Migrations built the way the schema update pipeline builds them
# ---------------------------------------------------------------------------


def build_attribute_migration(
    migration_cls: AttributeMigrationClass,
    branch: Branch,
    node_kind: str,
    attribute_name: str,
    **changes: Any,
) -> AttributeSchemaMigration:
    """Return a migration for `attribute_name` of `node_kind`, after `changes` are applied to the attribute."""
    schema = registry.schema.get_schema_branch(name=branch.name)
    previous_node = schema.get(name=node_kind)
    new_node = schema.duplicate().get(name=node_kind)
    new_attribute = new_node.get_attribute(name=attribute_name)
    previous_attribute = previous_node.get_attribute(name=attribute_name)
    # A schema registered without a database load has no ids, and a rename matches the attributes by id
    if previous_attribute.id is None:
        previous_attribute.id = new_attribute.id = f"{node_kind}-{attribute_name}"
    for field_name, value in changes.items():
        setattr(new_attribute, field_name, value)
    return migration_cls(
        previous_node_schema=previous_node,
        new_node_schema=new_node,
        schema_path=SchemaPath(
            path_type=SchemaPathType.ATTRIBUTE, schema_kind=node_kind, field_name=new_attribute.name
        ),
    )


def build_attribute_add_migration(
    migration_cls: AttributeMigrationClass, branch: Branch, kind: str, attribute: AttributeSchema
) -> AttributeSchemaMigration:
    schema = registry.schema.get_schema_branch(name=branch.name)
    previous_node = schema.get(name=kind)
    new_node = schema.duplicate().get(name=kind)
    new_node.attributes.append(attribute)
    return migration_cls(
        previous_node_schema=previous_node,
        new_node_schema=new_node,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind=kind, field_name=attribute.name),
    )


def build_node_kind_update_migration(branch: Branch, kind: str, **changes: Any) -> NodeKindUpdateMigration:
    schema = registry.schema.get_schema_branch(name=branch.name)
    previous_node = schema.get(name=kind)
    candidate_schema = schema.duplicate()
    new_node = candidate_schema.get(name=kind)
    candidate_schema.delete(name=kind)
    for field_name, value in changes.items():
        setattr(new_node, field_name, value)
    for other_kind in candidate_schema.node_names:
        other_node = candidate_schema.get(name=other_kind, duplicate=False)
        for relationship in other_node.relationships:
            if relationship.peer == kind:
                relationship.peer = new_node.kind
    candidate_schema.set(name=new_node.kind, schema=new_node)
    candidate_schema.process()
    return NodeKindUpdateMigration(
        previous_node_schema=previous_node,
        new_node_schema=new_node,
        derived_schemas=get_derived_schema_pairs(
            previous_schema_branch=schema,
            new_schema_branch=candidate_schema,
            previous_node_schema=previous_node,
            new_node_schema=new_node,
        ),
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind=new_node.kind, field_name=min(changes)),
    )


def build_node_remove_migration(branch: Branch, kind: str) -> NodeRemoveMigration:
    schema = registry.schema.get_schema_branch(name=branch.name)
    return NodeRemoveMigration(
        previous_node_schema=schema.get(name=kind),
        new_node_schema=None,
        schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind=kind),
    )


def build_relationship_remove_params(
    db: InfrahubDatabase, branch: Branch, node_kind: str, relationship_name: str
) -> tuple[NodeRelationshipRemoveMigration, RelationshipRemoveQueryParams]:
    """Drop both sides of a relationship of `node_kind` from the registered schema and return the migration inputs.

    Both sides must be gone first, or the migration skips every `Relationship` vertex.

    Raises:
        ValueError: When the migration finds no relationship data to close.

    """
    schema_branch = registry.schema.get_schema_branch(name=branch.name)
    previous_node = schema_branch.get(name=node_kind)
    identifier = previous_node.get_relationship(name=relationship_name).get_identifier()

    candidate = schema_branch.duplicate()
    for sharing_schema in candidate.get_schemas_by_rel_identifier(identifier=identifier):
        node_schema = candidate.get(name=sharing_schema.kind)
        node_schema.relationships = [rel for rel in node_schema.relationships if rel.identifier != identifier]
        candidate.set(name=sharing_schema.kind, schema=node_schema)
    registry.schema.set_schema_branch(name=branch.name, schema=candidate)

    migration = NodeRelationshipRemoveMigration(
        previous_node_schema=previous_node,
        new_node_schema=candidate.get(name=node_kind),
        schema_path=SchemaPath(
            path_type=SchemaPathType.RELATIONSHIP, schema_kind=node_kind, field_name=relationship_name
        ),
    )
    query_params = migration._build_query_params(db=db, branch=branch)
    if query_params is None:
        raise ValueError(f"no relationship data to close for {relationship_name}")
    return migration, query_params


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


async def changed_node_ids(db: InfrahubDatabase, kinds: list[str], at: Timestamp) -> dict[str, set[str]]:
    """Return, per kind, the uuids of the nodes of `kinds` that have an edge created or closed at `at`.

    An edge counts when it touches the node, or touches an Attribute or Relationship vertex linked to it.
    """
    query = """
    MATCH (n:Node)
    WHERE n.kind IN $kinds
    AND (
        EXISTS { MATCH (n)-[e]-() WHERE e.from = $at OR e.to = $at }
        OR EXISTS { MATCH (n)-[:HAS_ATTRIBUTE|IS_RELATED]-()-[e]-() WHERE e.from = $at OR e.to = $at }
    )
    RETURN n.kind AS kind, collect(DISTINCT n.uuid) AS ids
    """
    results = await db.execute_query(query=query, params={"kinds": kinds, "at": at.to_string()})
    return {result["kind"]: set(result["ids"]) for result in results}


async def assert_count_matches_write(
    db: InfrahubDatabase,
    queries: list[type[MigrationSelectionQuery]],
    init_kwargs: dict[str, Any],
    branch: Branch,
    expected: dict[str, int],
    population: list[str],
    check_remaining: bool = True,
) -> None:
    """Count with the last query, run every query in order, then check the count against the changes.

    The changes are read for every kind in `population`, so a kind the write changes but the count misses
    fails the check. With `check_remaining`, a count taken after the write must find nothing left to change.
    """
    at = Timestamp()
    instances = [await query_cls.init(db=db, branch=branch, at=at, **init_kwargs) for query_cls in queries]

    counted = await instances[-1].count_changes(db=db)
    for instance in instances:
        await instance.execute(db=db)

    assert counted == expected, f"counted {counted}, expected {expected}"
    changed = {kind: len(ids) for kind, ids in (await changed_node_ids(db=db, kinds=population, at=at)).items()}
    assert counted == changed, f"counted {counted}, the write changed {changed}"

    if not check_remaining:
        return
    recount = await queries[-1].init(db=db, branch=branch, at=Timestamp(), **init_kwargs)
    remaining = await recount.count_changes(db=db)
    assert remaining == {}, f"counted {remaining} after the write"
