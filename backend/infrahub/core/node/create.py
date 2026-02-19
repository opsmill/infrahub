from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping

from infrahub import lock
from infrahub.core import registry
from infrahub.core.constants import (
    SYSTEM_USER_ID,
    InfrahubKind,
    MetadataOptions,
    RelationshipCardinality,
    RelationshipKind,
)
from infrahub.core.constants.schema import RESOURCE_POOL_REL_SUFFIX
from infrahub.core.constraint.node.runner import NodeConstraintRunner
from infrahub.core.creation_context import NodeCreationContext
from infrahub.core.node import Node
from infrahub.core.node.lock_utils import get_lock_names_on_object_mutation
from infrahub.core.protocols import CoreObjectTemplate
from infrahub.core.relationship.model import PeerWithRelationshipMetadata
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
        return await template_relationship_manager.get_peers(
            db=db, peer_type=CoreObjectTemplate, include_metadata=MetadataOptions.SOURCE
        )

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
        if attr_name not in obj_peer_schema.attribute_names:
            continue

        template_attr = template_peer.get_attribute(name=attr_name)

        # NumberPool from_pool handling requires two code paths:
        # 1. Template just created in-memory: from_pool is set but not yet persisted
        # 2. Template loaded from DB: from_pool is not persisted, must reconstruct from source
        if template_attr.from_pool:
            obj_peer_data[attr_name] = {"from_pool": template_attr.from_pool}
            continue

        if template_attr.value is None and template_attr.source_id:  # type: ignore
            source = await template_attr.get_source(db=db)
            if source and source.get_kind() == InfrahubKind.NUMBERPOOL:
                obj_peer_data[attr_name] = {"from_pool": {"id": source.id}}
                continue

        if template_attr.value is None:
            continue
        if template_attr.is_default:
            # if template attr is_default and the value matches the object schema, then do not set the source
            try:
                if obj_peer_schema.get_attribute(name=attr_name).default_value == template_attr.value:
                    continue
            except ValueError:
                pass

        # If the template attribute comes from a profile, preserve the profile as the source
        # Otherwise, use the template itself as the source
        source_id = template_attr.source_id or template_peer.id  # type: ignore
        attr_data = {"value": template_attr.value, "source": source_id}
        if template_attr.is_from_profile:
            attr_data["is_from_profile"] = True
        obj_peer_data[attr_name] = attr_data

    for rel in template_peer.get_schema().relationship_names:
        rel_manager: RelationshipManager = getattr(template_peer, rel)
        if (
            rel_manager.schema.kind
            not in [
                RelationshipKind.COMPONENT,
                RelationshipKind.PARENT,
                RelationshipKind.PROFILE,
                RelationshipKind.ATTRIBUTE,
            ]
            or rel_manager.schema.name not in obj_peer_schema.relationship_names
        ):
            continue

        peers_map = await rel_manager.get_peers(db=db)
        if rel_manager.schema.kind in [
            RelationshipKind.COMPONENT,
            RelationshipKind.PARENT,
            RelationshipKind.PROFILE,
        ] and list(peers_map.keys()) == [current_template.id]:
            obj_peer_data[rel] = {"id": parent_obj.id}
            continue

        rel_peer_ids = []
        for peer_id, peer_object in peers_map.items():
            # deeper templates are handled in the next level of recursion
            if peer_object.get_schema().is_template_schema:
                continue
            rel_peer_ids.append({"id": peer_id})

        # Only set the relationship data if there are actual peers to set
        if rel_peer_ids:
            obj_peer_data[rel] = rel_peer_ids

        if rel_manager.schema.kind == RelationshipKind.PROFILE:
            profiles = list(await rel_manager.get_peers(db=db))
            obj_peer_data[rel] = profiles

    return obj_peer_data


async def allocate_from_resource_pools(
    db: InfrahubDatabase,
    branch: Branch,
    obj: Node,
    template: CoreObjectTemplate,
    at: Timestamp | None = None,
    user_id: str = SYSTEM_USER_ID,
) -> None:
    """Allocate resources from template's _from_resource_pool relationships to the object."""
    template_schema = template.get_schema()
    obj_schema = obj.get_schema()

    for rel_schema in template_schema.relationships:
        if not rel_schema.name.endswith(RESOURCE_POOL_REL_SUFFIX):
            continue

        original_rel_name = rel_schema.name.removesuffix(RESOURCE_POOL_REL_SUFFIX)

        if original_rel_name not in obj_schema.relationship_names:
            continue

        pool_rel_manager = template.get_relationship(name=rel_schema.name)
        pool = await pool_rel_manager.get_peer(db=db)
        if not pool:
            continue

        allocated_resource = await pool.get_resource(db=db, branch=branch, identifier=obj.id, at=at, user_id=user_id)  # type: ignore
        NodeCreationContext.record_if_active(node=allocated_resource)

        obj_rel_manager = obj.get_relationship(name=original_rel_name)
        await obj_rel_manager.update(
            data=PeerWithRelationshipMetadata(peer=allocated_resource, source_id=pool.id), db=db
        )


async def handle_template_relationships(
    db: InfrahubDatabase,
    branch: Branch,
    obj: Node,
    template: CoreObjectTemplate,
    fields: list,
    constraint_runner: NodeConstraintRunner | None = None,
    at: Timestamp | None = None,
    user_id: str = SYSTEM_USER_ID,
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

            await allocate_from_resource_pools(
                db=db, branch=branch, obj=obj_peer, template=template_relationship_peer, at=at, user_id=user_id
            )

            template_profile_ids = await get_profile_ids(db=db, obj=template_relationship_peer)
            if template_profile_ids:
                node_profiles_applier = NodeProfilesApplier(db=db, branch=branch)
                await node_profiles_applier.apply_profiles(node=obj_peer)

            await obj_peer.save(db=db, user_id=user_id)
            NodeCreationContext.record_if_active(node=obj_peer)

            await handle_template_relationships(
                db=db,
                branch=branch,
                constraint_runner=constraint_runner,
                obj=obj_peer,
                template=template_relationship_peer,
                fields=fields,
                at=at,
                user_id=user_id,
            )


async def get_profile_ids(db: InfrahubDatabase, obj: Node | CoreObjectTemplate) -> set[str]:
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
    user_id: str = SYSTEM_USER_ID,
) -> Node:
    obj = await node_class.init(db=db, schema=schema, branch=branch)
    await obj.new(db=db, **data)
    await node_constraint_runner.check(node=obj, field_filters=fields_to_validate)
    await obj.save(db=db, at=at, user_id=user_id)

    object_template = await obj.get_object_template(db=db)
    if object_template:
        await handle_template_relationships(
            db=db,
            branch=branch,
            template=object_template,
            obj=obj,
            fields=fields_to_validate,
            at=at,
            user_id=user_id,
        )
    return obj


async def create_node(
    data: dict[str, Any],
    db: InfrahubDatabase,
    branch: Branch,
    schema: MainSchemaTypes,
    at: Timestamp | None = None,
    user_id: str = SYSTEM_USER_ID,
) -> Node:
    """Create a node in the database if constraint checks succeed."""

    if isinstance(schema, GenericSchema):
        raise ValueError(f"Node of generic schema `{schema.name=}` can not be instantiated.")

    component_registry = get_component_registry()
    node_class = Node
    if schema.kind in registry.node:
        node_class = registry.node[schema.kind]

    fields_to_validate = list(data)

    preview_obj = await node_class.init(db=db, schema=schema, branch=branch)
    await preview_obj.new(db=db, process_pools=False, **data)
    schema_branch = db.schema.get_schema_branch(name=branch.name)
    lock_names = get_lock_names_on_object_mutation(node=preview_obj, schema_branch=schema_branch)

    obj: Node
    creation_context = NodeCreationContext()
    async with InfrahubMultiLock(lock_registry=lock.registry, locks=lock_names, metrics=False):
        if db.is_transaction:
            node_constraint_runner = await component_registry.get_component(NodeConstraintRunner, db=db, branch=branch)

            with creation_context:
                obj = await _do_create_node(
                    node_class=node_class,
                    node_constraint_runner=node_constraint_runner,
                    db=db,
                    schema=schema,
                    branch=branch,
                    fields_to_validate=fields_to_validate,
                    data=data,
                    at=at,
                    user_id=user_id,
                )
        else:
            async with db.start_transaction() as dbt:
                node_constraint_runner = await component_registry.get_component(
                    NodeConstraintRunner, db=dbt, branch=branch
                )

                with creation_context:
                    obj = await _do_create_node(
                        node_class=node_class,
                        node_constraint_runner=node_constraint_runner,
                        db=dbt,
                        schema=schema,
                        branch=branch,
                        fields_to_validate=fields_to_validate,
                        data=data,
                        at=at,
                        user_id=user_id,
                    )

    obj._creation_context = creation_context

    if await get_profile_ids(db=db, obj=obj):
        node_profiles_applier = NodeProfilesApplier(db=db, branch=branch)
        await node_profiles_applier.apply_profiles(node=obj)
        await obj.save(db=db, user_id=user_id)

    return obj
