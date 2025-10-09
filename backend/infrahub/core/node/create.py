from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping

from infrahub import lock
from infrahub.core import registry
from infrahub.core.constants import RelationshipCardinality, RelationshipKind
from infrahub.core.constraint.node.runner import NodeConstraintRunner
from infrahub.core.node import Node
from infrahub.core.node.lock_utils import get_kind_lock_names_on_object_mutation
from infrahub.core.protocols import CoreObjectTemplate
from infrahub.core.schema import GenericSchema
from infrahub.dependencies.registry import get_component_registry
from infrahub.lock import InfrahubMultiLock
from infrahub.profiles.node_applier import NodeProfilesApplier

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.relationship.model import RelationshipManager
    from infrahub.core.schema import MainSchemaTypes, NonGenericSchemaTypes, RelationshipSchema
    from infrahub.core.timestamp import Timestamp
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

    for attr_name in template_peer.get_schema().attribute_names:
        template_attr = getattr(template_peer, attr_name)
        if template_attr.value is None:
            continue
        if template_attr.is_default:
            # if template attr is_default and the value matches the object schema, then do not set the source
            try:
                if obj_peer_schema.get_attribute(name=attr_name).default_value == template_attr.value:
                    continue
            except ValueError:
                pass

        obj_peer_data[attr_name] = {"value": template_attr.value, "source": template_peer.id}

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
    at: Timestamp | None = None,
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

            obj_peer = await Node.init(schema=obj_peer_schema, db=db, branch=branch, at=at)
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
                at=at,
            )


async def get_profile_ids(db: InfrahubDatabase, obj: Node) -> set[str]:
    if not hasattr(obj, "profiles"):
        return set()
    profile_rels = await obj.profiles.get_relationships(db=db)
    return {pr.peer_id for pr in profile_rels}


async def _do_create_node(
    node_class: type[Node],
    node_constraint_runner: NodeConstraintRunner,
    db: InfrahubDatabase,
    schema: NonGenericSchemaTypes,
    branch: Branch,
    fields_to_validate: list[str],
    data: dict[str, Any],
    at: Timestamp | None = None,
) -> Node:
    obj = await node_class.init(db=db, schema=schema, branch=branch)
    await obj.new(db=db, **data)
    await node_constraint_runner.check(node=obj, field_filters=fields_to_validate)
    await obj.save(db=db, at=at)

    object_template = await obj.get_object_template(db=db)
    if object_template:
        await handle_template_relationships(
            db=db,
            branch=branch,
            template=object_template,
            obj=obj,
            fields=fields_to_validate,
            at=at,
        )
    return obj


async def _do_create_node_with_lock(
    node_class: type[Node],
    node_constraint_runner: NodeConstraintRunner,
    db: InfrahubDatabase,
    schema: NonGenericSchemaTypes,
    branch: Branch,
    fields_to_validate: list[str],
    data: dict[str, Any],
    at: Timestamp | None = None,
) -> Node:
    schema_branch = registry.schema.get_schema_branch(name=branch.name)
    lock_names = get_kind_lock_names_on_object_mutation(
        kind=schema.kind, branch=branch, schema_branch=schema_branch, data=dict(data)
    )

    if lock_names:
        async with InfrahubMultiLock(lock_registry=lock.registry, locks=lock_names):
            return await _do_create_node(
                node_class=node_class,
                node_constraint_runner=node_constraint_runner,
                db=db,
                schema=schema,
                branch=branch,
                fields_to_validate=fields_to_validate,
                data=data,
                at=at,
            )
    return await _do_create_node(
        node_class=node_class,
        node_constraint_runner=node_constraint_runner,
        db=db,
        schema=schema,
        branch=branch,
        fields_to_validate=fields_to_validate,
        data=data,
        at=at,
    )


async def create_node(
    data: dict[str, Any],
    db: InfrahubDatabase,
    branch: Branch,
    schema: MainSchemaTypes,
    at: Timestamp | None = None,
) -> Node:
    """Create a node in the database if constraint checks succeed."""

    if isinstance(schema, GenericSchema):
        raise ValueError(f"Node of generic schema `{schema.name=}` can not be instantiated.")

    component_registry = get_component_registry()
    node_constraint_runner = await component_registry.get_component(
        NodeConstraintRunner, db=db.start_session() if not db.is_transaction else db, branch=branch
    )
    node_class = Node
    if schema.kind in registry.node:
        node_class = registry.node[schema.kind]

    fields_to_validate = list(data)
    if db.is_transaction:
        obj = await _do_create_node_with_lock(
            node_class=node_class,
            node_constraint_runner=node_constraint_runner,
            db=db,
            schema=schema,
            branch=branch,
            fields_to_validate=fields_to_validate,
            data=data,
            at=at,
        )
    else:
        async with db.start_transaction() as dbt:
            obj = await _do_create_node_with_lock(
                node_class=node_class,
                node_constraint_runner=node_constraint_runner,
                db=dbt,
                schema=schema,
                branch=branch,
                fields_to_validate=fields_to_validate,
                data=data,
                at=at,
            )

    if await get_profile_ids(db=db, obj=obj):
        node_profiles_applier = NodeProfilesApplier(db=db, branch=branch)
        await node_profiles_applier.apply_profiles(node=obj)
        await obj.save(db=db)

    return obj
