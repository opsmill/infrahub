from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping

from infrahub.core import registry
from infrahub.core.constants import RelationshipCardinality, RelationshipKind
from infrahub.core.constraint.node.runner import NodeConstraintRunner
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreObjectTemplate
from infrahub.dependencies.registry import get_component_registry

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.relationship.model import RelationshipManager
    from infrahub.core.schema import MainSchemaTypes, NonGenericSchemaTypes, RelationshipSchema
    from infrahub.database import InfrahubDatabase


async def get_template_relationship_peers(
    db: InfrahubDatabase, template: CoreObjectTemplate, relationship: RelationshipSchema
) -> Mapping[str, CoreObjectTemplate]:
    """For a given relationship on the template, fetch the related peers."""
    template_relationship_manager: RelationshipManager = getattr(template, relationship.name)
    if relationship.cardinality == RelationshipCardinality.MANY:
        return await template_relationship_manager.get_peers(db=db, peer_type=CoreObjectTemplate)

    peers: dict[str, CoreObjectTemplate] = {}
    template_relationship_peer = await template_relationship_manager.get_peer(db=db, peer_type=CoreObjectTemplate)
    if template_relationship_peer:
        peers[template_relationship_peer.id] = template_relationship_peer
    return peers


async def extract_peer_data(
    db: InfrahubDatabase,
    template_peer: CoreObjectTemplate,
    obj_peer_schema: MainSchemaTypes,
    parent_obj: Node,
    current_template: CoreObjectTemplate,
) -> Mapping[str, Any]:
    obj_peer_data: dict[str, Any] = {}

    for attr in template_peer.get_schema().attribute_names:
        if attr not in obj_peer_schema.attribute_names:
            continue
        obj_peer_data[attr] = {"value": getattr(template_peer, attr).value, "source": template_peer.id}

    for rel in template_peer.get_schema().relationship_names:
        rel_manager: RelationshipManager = getattr(template_peer, rel)
        if (
            rel_manager.schema.kind not in [RelationshipKind.COMPONENT, RelationshipKind.PARENT]
            or rel_manager.schema.name not in obj_peer_schema.relationship_names
        ):
            continue

        if list(await rel_manager.get_peers(db=db)) == [current_template.id]:
            obj_peer_data[rel] = {"id": parent_obj.id}

    return obj_peer_data


async def handle_template_relationships(
    db: InfrahubDatabase,
    branch: Branch,
    obj: Node,
    template: CoreObjectTemplate,
    fields: list,
    constraint_runner: NodeConstraintRunner | None = None,
) -> None:
    if constraint_runner is None:
        component_registry = get_component_registry()
        constraint_runner = await component_registry.get_component(NodeConstraintRunner, db=db, branch=branch)

    for relationship in obj.get_relationships(kind=RelationshipKind.COMPONENT, exclude=fields):
        template_relationship_peers = await get_template_relationship_peers(
            db=db, template=template, relationship=relationship
        )
        if not template_relationship_peers:
            continue

        for template_relationship_peer in template_relationship_peers.values():
            # We retrieve peer schema for each peer in case we are processing a relationship which is based on a generic
            obj_peer_schema = registry.schema.get_node_schema(
                name=template_relationship_peer.get_schema().kind.removeprefix("Template"),
                branch=branch,
                duplicate=False,
            )
            obj_peer_data = await extract_peer_data(
                db=db,
                template_peer=template_relationship_peer,
                obj_peer_schema=obj_peer_schema,
                parent_obj=obj,
                current_template=template,
            )

            obj_peer = await Node.init(schema=obj_peer_schema, db=db, branch=branch)
            await obj_peer.new(db=db, **obj_peer_data)
            await constraint_runner.check(node=obj_peer, field_filters=list(obj_peer_data))
            await obj_peer.save(db=db)

            await handle_template_relationships(
                db=db,
                branch=branch,
                constraint_runner=constraint_runner,
                obj=obj_peer,
                template=template_relationship_peer,
                fields=fields,
            )


async def get_profile_ids(db: InfrahubDatabase, obj: Node) -> set[str]:
    if not hasattr(obj, "profiles"):
        return set()
    profile_rels = await obj.profiles.get_relationships(db=db)
    return {pr.peer_id for pr in profile_rels}


async def refresh_for_profile_update(
    db: InfrahubDatabase,
    branch: Branch,
    obj: Node,
    schema: NonGenericSchemaTypes,
    previous_profile_ids: set[str] | None = None,
) -> Node:
    if not hasattr(obj, "profiles"):
        return obj
    current_profile_ids = await get_profile_ids(db=db, obj=obj)
    if previous_profile_ids is None or previous_profile_ids != current_profile_ids:
        refreshed_node = await NodeManager.get_one_by_id_or_default_filter(
            db=db,
            kind=schema.kind,
            id=obj.get_id(),
            branch=branch,
            include_owner=True,
            include_source=True,
        )
        refreshed_node._node_changelog = obj.node_changelog
        return refreshed_node
    return obj


async def _do_create_node(
    node_class: type[Node],
    db: InfrahubDatabase,
    data: dict,
    schema: NonGenericSchemaTypes,
    fields_to_validate: list,
    branch: Branch,
    node_constraint_runner: NodeConstraintRunner,
) -> Node:
    obj = await node_class.init(db=db, schema=schema, branch=branch)
    await obj.new(db=db, **data)
    await node_constraint_runner.check(node=obj, field_filters=fields_to_validate)
    await obj.save(db=db)

    object_template = await obj.get_object_template(db=db)
    if object_template:
        await handle_template_relationships(
            db=db,
            branch=branch,
            template=object_template,
            obj=obj,
            fields=fields_to_validate,
        )
    return obj


async def create_node(
    data: dict,
    db: InfrahubDatabase,
    branch: Branch,
    schema: NonGenericSchemaTypes,
) -> Node:
    """Create a node in the database if constraint checks succeed."""

    component_registry = get_component_registry()
    node_constraint_runner = await component_registry.get_component(
        NodeConstraintRunner, db=db.start_session() if not db.is_transaction else db, branch=branch
    )
    node_class = Node
    if schema.kind in registry.node:
        node_class = registry.node[schema.kind]

    fields_to_validate = list(data)
    if db.is_transaction:
        obj = await _do_create_node(
            node_class=node_class,
            node_constraint_runner=node_constraint_runner,
            db=db,
            schema=schema,
            branch=branch,
            fields_to_validate=fields_to_validate,
            data=data,
        )
    else:
        async with db.start_transaction() as dbt:
            obj = await _do_create_node(
                node_class=node_class,
                node_constraint_runner=node_constraint_runner,
                db=dbt,
                schema=schema,
                branch=branch,
                fields_to_validate=fields_to_validate,
                data=data,
            )

    if await get_profile_ids(db=db, obj=obj):
        obj = await refresh_for_profile_update(db=db, branch=branch, schema=schema, obj=obj)

    return obj
