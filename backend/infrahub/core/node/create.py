from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterable, Mapping, cast, overload

from infrahub import lock
from infrahub.core import registry
from infrahub.core.constants import (
    PROFILES_RELATIONSHIP_NAME,
    SYSTEM_USER_ID,
    MetadataOptions,
    RelationshipKind,
)
from infrahub.core.constants.schema import RESOURCE_POOL_REL_SUFFIX
from infrahub.core.constraint.node.runner import NodeConstraintRunner
from infrahub.core.creation_context import NodeCreationContext
from infrahub.core.node import Node
from infrahub.core.node.lock_utils import get_lock_names_on_object_mutation
from infrahub.core.protocols_base import CoreNode
from infrahub.core.relationship.model import PeerWithRelationshipMetadata
from infrahub.core.schema import GenericSchema
from infrahub.dependencies.registry import get_component_registry
from infrahub.lock import InfrahubMultiLock
from infrahub.profiles.node_applier import NodeProfilesApplier
from infrahub.templates.node_applier import get_relationship_names_to_read

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node import SchemaProtocol
    from infrahub.core.protocols import CoreObjectTemplate
    from infrahub.core.relationship.model import Relationship, RelationshipManager
    from infrahub.core.schema import MainSchemaTypes, NonGenericSchemaTypes
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


async def get_component_subtemplates(
    db: InfrahubDatabase, obj: Node, template: CoreObjectTemplate, fields: list
) -> list[CoreObjectTemplate]:
    """The subtemplates the component relationships of this template name.

    The template was read with those relationships and with the peers they name, so naming its
    subtemplates costs no query.
    """
    subtemplates: list[CoreObjectTemplate] = []
    for relationship in obj.get_relationships(kind=RelationshipKind.COMPONENT, exclude=fields):
        template_relationship_manager: RelationshipManager = getattr(template, relationship.name)
        for template_relationship in await template_relationship_manager.get_relationships(db=db):
            subtemplates.append(cast("CoreObjectTemplate", await template_relationship.get_peer(db=db)))
    return subtemplates


async def read_subtemplates(db: InfrahubDatabase, branch: Branch, subtemplates: list[CoreObjectTemplate]) -> None:
    """Read a whole level of subtemplates, with the relationships materializing them consults.

    The peers those relationships name are read with them, which is what leaves the level below
    already in memory by the time it is walked.
    """
    await registry.manager.prefetch_relationships(
        db=db,
        nodes=cast("Iterable[Node]", subtemplates),
        names={
            name
            for subtemplate in subtemplates
            for name in get_relationship_names_to_read(schema=subtemplate.get_schema())
        },
        branch=branch,
        include_metadata=MetadataOptions.SOURCE,
    )


async def _peer_is_a_template(db: InfrahubDatabase, relationship: Relationship) -> bool:
    """Whether the peer of this relationship is a template, reading it only when its kind is unknown."""
    peer_kind = relationship.get_concrete_peer_kind()
    if peer_kind is None:
        peer = await relationship.get_peer(db=db)
        return peer.get_schema().is_template_schema

    return db.schema.get(name=peer_kind, branch=relationship.branch, duplicate=False).is_template_schema


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

    for rel_name in template_peer.get_schema().relationship_names:
        rel_manager: RelationshipManager = getattr(template_peer, rel_name)
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

        # The peers are named by their id and their kind, both of which the relationships carry.
        relationships = [
            relationship for relationship in await rel_manager.get_relationships(db=db) if relationship.peer_id
        ]
        peer_ids = [relationship.peer_id for relationship in relationships]
        if rel_manager.schema.kind in [
            RelationshipKind.COMPONENT,
            RelationshipKind.PARENT,
            RelationshipKind.PROFILE,
        ] and peer_ids == [current_template.id]:
            # This relationship points back at the template being applied, so the peer on the new
            # object is the node created from that template — which the caller holds. Hand the node
            # over, so every step that needs the peer already has it.
            obj_peer_data[rel_name] = parent_obj
            continue

        rel_peer_ids = []
        for relationship in relationships:
            # deeper templates are handled in the next level of recursion
            if await _peer_is_a_template(db=db, relationship=relationship):
                continue
            rel_peer_ids.append({"id": relationship.peer_id})

        # Only set the relationship data if there are actual peers to set
        if rel_peer_ids:
            obj_peer_data[rel_name] = rel_peer_ids

        if rel_manager.schema.kind == RelationshipKind.PROFILE:
            obj_peer_data[rel_name] = peer_ids

    return obj_peer_data


async def allocate_from_resource_pools(
    db: InfrahubDatabase,
    branch: Branch,
    obj: Node,
    template: CoreObjectTemplate,
    at: Timestamp | None = None,
    user_id: str = SYSTEM_USER_ID,
) -> None:
    """Allocate resources from template's _from_resource_pool relationships to the object.

    Handles two cases:
    - Relationship pools (IP address/prefix): allocates a new node and sets it as the relationship peer
    - Attribute pools (Number): allocates a value and sets it on the attribute
    The pool is set as the source of the attribute/relationship in either case
    """
    template_schema = template.get_schema()
    obj_schema = obj.get_schema()

    for rel_schema in template_schema.relationships:
        if not rel_schema.name.endswith(RESOURCE_POOL_REL_SUFFIX):
            continue

        original_name = rel_schema.name.removesuffix(RESOURCE_POOL_REL_SUFFIX)

        pool_rel_manager = template.get_relationship(name=rel_schema.name)
        pool = await pool_rel_manager.get_peer(db=db)
        if not pool:
            continue

        if original_name in obj_schema.attribute_names:
            # Number pool: allocate a value and set it on the attribute
            attr_schema = obj_schema.get_attribute(name=original_name)
            allocated_value = await pool.get_resource(  # type: ignore[attr-defined]
                db=db, branch=branch, identifier=obj.get_id(), attribute=attr_schema
            )  # type: ignore
            attribute = obj.get_attribute(name=original_name)
            attribute.value = allocated_value
            attribute.is_default = False
            attribute.source = pool.id  # type: ignore[assignment]
        elif original_name in obj_schema.relationship_names:
            # IP pool: allocate a node and set it as the relationship peer
            allocated_resource = await pool.get_resource(  # type: ignore[attr-defined]
                db=db, branch=branch, identifier=obj.get_id(), at=at, user_id=user_id
            )  # type: ignore
            NodeCreationContext.record_if_active(node=allocated_resource)

            obj_rel_manager = obj.get_relationship(name=original_name)
            await obj_rel_manager.update(
                data=PeerWithRelationshipMetadata(peer=allocated_resource, source_id=pool.id), db=db
            )


async def create_component(
    db: InfrahubDatabase,
    branch: Branch,
    constraint_runner: NodeConstraintRunner,
    parent_obj: Node,
    parent_template: CoreObjectTemplate,
    subtemplate: CoreObjectTemplate,
    at: Timestamp | None = None,
    user_id: str = SYSTEM_USER_ID,
) -> Node:
    """Create the object a subtemplate describes, as a component of the object holding it."""
    # We retrieve peer schema for each peer in case we are processing a relationship which is based on a generic
    obj_peer_schema = registry.schema.get_node_schema(
        name=subtemplate.get_schema().kind.removeprefix("Template"),
        branch=branch,
        duplicate=False,
    )
    obj_peer_data = await extract_peer_data(
        db=db,
        template_peer=subtemplate,
        obj_peer_schema=obj_peer_schema,
        parent_obj=parent_obj,
        current_template=parent_template,
    )

    obj_peer = await Node.init(schema=obj_peer_schema, db=db, branch=branch, at=at)
    await obj_peer.new(db=db, **obj_peer_data)
    await constraint_runner.check(node=obj_peer, field_filters=list(obj_peer_data))

    await allocate_from_resource_pools(db=db, branch=branch, obj=obj_peer, template=subtemplate, at=at, user_id=user_id)

    template_profile_ids = await get_profile_ids(db=db, obj=subtemplate)
    if template_profile_ids:
        node_profiles_applier = NodeProfilesApplier(db=db, branch=branch)
        await node_profiles_applier.apply_profiles(node=obj_peer)

    await obj_peer.save(db=db, user_id=user_id)
    NodeCreationContext.record_if_active(node=obj_peer)
    return obj_peer


async def handle_template_relationships(
    db: InfrahubDatabase,
    branch: Branch,
    obj: Node,
    template: CoreObjectTemplate,
    fields: list,
    at: Timestamp | None = None,
    user_id: str = SYSTEM_USER_ID,
) -> None:
    """Create the objects the components of a template describe, one level of the template at a time.

    The subtemplates of a level are all named before any of them is walked, so the level is read
    once for every parent it hangs from rather than once per parent. `template` itself was read that
    way by the caller, which is why the walk starts with a level already in memory.
    """
    component_registry = get_component_registry()
    constraint_runner = await component_registry.get_component(NodeConstraintRunner, db=db, branch=branch)

    level: list[tuple[Node, CoreObjectTemplate]] = [(obj, template)]
    while level:
        parents_with_subtemplates: list[tuple[Node, CoreObjectTemplate, list[CoreObjectTemplate]]] = []
        for parent_obj, parent_template in level:
            subtemplates = await get_component_subtemplates(
                db=db, obj=parent_obj, template=parent_template, fields=fields
            )
            parents_with_subtemplates.append((parent_obj, parent_template, subtemplates))

        level_subtemplates = [
            subtemplate for _, _, subtemplates in parents_with_subtemplates for subtemplate in subtemplates
        ]
        if not level_subtemplates:
            return

        await read_subtemplates(db=db, branch=branch, subtemplates=level_subtemplates)

        next_level: list[tuple[Node, CoreObjectTemplate]] = []
        for parent_obj, parent_template, subtemplates in parents_with_subtemplates:
            for subtemplate in subtemplates:
                obj_peer = await create_component(
                    db=db,
                    branch=branch,
                    constraint_runner=constraint_runner,
                    parent_obj=parent_obj,
                    parent_template=parent_template,
                    subtemplate=subtemplate,
                    at=at,
                    user_id=user_id,
                )
                next_level.append((obj_peer, subtemplate))
        level = next_level


async def get_profile_ids(db: InfrahubDatabase, obj: Node | CoreObjectTemplate) -> set[str]:
    if not hasattr(obj, "profiles"):
        return set()
    profile_rels = await obj.profiles.get_relationships(db=db)
    return {pr.peer_id for pr in profile_rels}


def _has_profiles_set(node: Node) -> bool:
    """Whether the node was built with profiles, named by its payload or copied from its template.

    A relationship manager initialised with data is marked as fetched, so this reads nothing.
    """
    if not hasattr(node, PROFILES_RELATIONSHIP_NAME):
        return False
    profiles = node.get_relationship(PROFILES_RELATIONSHIP_NAME)
    if not profiles.has_fetched_relationships:
        # Nothing populated this manager, so the node was built without profiles. Counting the peers
        # is not an option: `len()` raises on a manager whose peers have never been read.
        return False
    return len(profiles) > 0


async def _do_create_node(
    node_class: type[Node],
    node_constraint_runner: NodeConstraintRunner,
    creation_context: NodeCreationContext,
    db: InfrahubDatabase,
    schema: NonGenericSchemaTypes,
    branch: Branch,
    fields_to_validate: list[str],
    data: dict[str, Any],
    at: Timestamp | None = None,
    user_id: str = SYSTEM_USER_ID,
    object_template: CoreObjectTemplate | None = None,
) -> Node:
    with creation_context:
        obj = await node_class.init(db=db, schema=schema, branch=branch)
        obj._object_template = object_template
        await obj.new(db=db, **data)
        await node_constraint_runner.check(node=obj, field_filters=fields_to_validate)
        await obj.save(db=db, at=at, user_id=user_id)

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

    obj._creation_context = creation_context
    return obj


@overload
async def create_node(
    data: dict[str, Any],
    db: InfrahubDatabase,
    branch: Branch,
    schema: type[SchemaProtocol],
    at: Timestamp | None = ...,
    user_id: str = ...,
) -> SchemaProtocol: ...


@overload
async def create_node(
    data: dict[str, Any],
    db: InfrahubDatabase,
    branch: Branch,
    schema: MainSchemaTypes,
    at: Timestamp | None = ...,
    user_id: str = ...,
) -> Node: ...


async def create_node(
    data: dict[str, Any],
    db: InfrahubDatabase,
    branch: Branch,
    schema: MainSchemaTypes | type[SchemaProtocol],
    at: Timestamp | None = None,
    user_id: str = SYSTEM_USER_ID,
) -> Node | SchemaProtocol:
    """Create a node in the database if constraint checks succeed.

    A schema protocol class may be passed instead of a schema object; the return type is then
    narrowed to that protocol.

    Raises:
        ValueError: When the schema is a `GenericSchema` and cannot be instantiated, or when a
            class that is not a node schema protocol is passed.

    """
    if isinstance(schema, type):
        if not issubclass(schema, CoreNode):
            raise ValueError(f"Invalid schema class provided: {schema!r}")
        schema = db.schema.get(name=schema.__name__, branch=branch)
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
    # The preview read the object template to work out the lock names; the node created under the
    # lock is built from that same template rather than reading it again.
    object_template = preview_obj._object_template

    obj: Node
    creation_context = NodeCreationContext()
    async with InfrahubMultiLock(lock_registry=lock.registry, locks=lock_names, metrics=False):
        if db.is_transaction:
            node_constraint_runner = await component_registry.get_component(NodeConstraintRunner, db=db, branch=branch)

            obj = await _do_create_node(
                node_class=node_class,
                node_constraint_runner=node_constraint_runner,
                creation_context=creation_context,
                db=db,
                schema=schema,
                branch=branch,
                fields_to_validate=fields_to_validate,
                data=data,
                at=at,
                user_id=user_id,
                object_template=object_template,
            )
        else:
            async with db.start_transaction() as dbt:
                node_constraint_runner = await component_registry.get_component(
                    NodeConstraintRunner, db=dbt, branch=branch
                )

                obj = await _do_create_node(
                    node_class=node_class,
                    node_constraint_runner=node_constraint_runner,
                    creation_context=creation_context,
                    db=dbt,
                    schema=schema,
                    branch=branch,
                    fields_to_validate=fields_to_validate,
                    data=data,
                    at=at,
                    user_id=user_id,
                    object_template=object_template,
                )

    # The node was written from its in-memory state, so the profiles it is linked to are the ones
    # its payload or its template set on it; there is nothing to read back.
    if _has_profiles_set(node=obj):
        node_profiles_applier = NodeProfilesApplier(db=db, branch=branch)
        await node_profiles_applier.apply_profiles(node=obj)
        await obj.save(db=db, user_id=user_id)

    return obj
