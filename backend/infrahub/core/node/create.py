from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast, overload

from infrahub_sdk.uuidt import UUIDT

from infrahub import lock
from infrahub.core import registry
from infrahub.core.attribute import PayloadPresence
from infrahub.core.constants import (
    PROFILES_RELATIONSHIP_NAME,
    SYSTEM_USER_ID,
    MetadataOptions,
    MutationAction,
    PoolRecordProvenance,
    RelationshipKind,
)
from infrahub.core.constants.schema import RESOURCE_POOL_REL_SUFFIX
from infrahub.core.constraint.node.runner import NodeConstraintRunner
from infrahub.core.mutation_context import NodeMutationContext
from infrahub.core.node import Node
from infrahub.core.node.lock_utils import get_lock_names_on_object_mutation, get_pool_lock_names, ip_pool_lock_name
from infrahub.core.protocols_base import CoreNode
from infrahub.core.query.resource_manager import TrackingPool
from infrahub.core.relationship.model import PeerWithRelationshipMetadata
from infrahub.core.schema import GenericSchema
from infrahub.dependencies.registry import get_component_registry
from infrahub.lock import InfrahubMultiLock
from infrahub.pools.attribute_pool_applier_factory import build_attribute_pool_applier
from infrahub.pools.number_pool_locker import picking_lock_name
from infrahub.pools.scope import AllocationScope
from infrahub.profiles.data_reader import ProfileDataReader
from infrahub.profiles.mandatory_fields_checker import ProfilesMandatoryFieldGetter
from infrahub.profiles.node_applier import NodeProfilesApplier
from infrahub.templates.node_applier import get_relationship_names_to_read

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable, Mapping

    from infrahub.core.branch import Branch
    from infrahub.core.node import SchemaProtocol
    from infrahub.core.protocols import CoreObjectTemplate
    from infrahub.core.relationship.model import Relationship, RelationshipManager
    from infrahub.core.schema import MainSchemaTypes, NonGenericSchemaTypes
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase
    from infrahub.pools.attribute_pool_applier import AttributePoolApplier, AttributePoolApplierInterface


@dataclass
class TemplateComponent:
    """A subtemplate to materialize, the schema of the object it describes, and what it holds.

    `components` is filled in once the level below this subtemplate has been read. `object_id` is the uuid of the
    object to create, set before the object exists so that the locks of the create can name it.
    """

    subtemplate: CoreObjectTemplate
    schema: NonGenericSchemaTypes
    components: list[TemplateComponent] = field(default_factory=list)
    object_id: str = field(default_factory=lambda: str(UUIDT()))


@dataclass
class _SubtemplateParent:
    """A template of the level being walked, and the list its components are recorded in."""

    schema: MainSchemaTypes
    template: CoreObjectTemplate
    components: list[TemplateComponent]


async def get_component_subtemplates(
    db: InfrahubDatabase, schema: MainSchemaTypes, template: CoreObjectTemplate, fields: list
) -> list[CoreObjectTemplate]:
    """The subtemplates the component relationships of this template name.

    The template was read with those relationships and with the peers they name, so naming its
    subtemplates costs no query.
    """
    subtemplates: list[CoreObjectTemplate] = []
    for relationship in schema.relationships:
        if relationship.kind != RelationshipKind.COMPONENT or relationship.name in fields:
            continue
        template_relationship_manager: RelationshipManager = getattr(template, relationship.name)
        for template_relationship in await template_relationship_manager.get_relationships(db=db):
            subtemplates.append(cast("CoreObjectTemplate", await template_relationship.get_peer(db=db)))
    return subtemplates


async def read_subtemplates(db: InfrahubDatabase, branch: Branch, subtemplates: list[CoreObjectTemplate]) -> None:
    """Read a whole level of subtemplates, with the relationships materializing them consults.

    The peers those relationships name are read with them, which is what leaves the level below
    already in memory by the time it is walked. Those peers include the parents the level points
    back at, which the walk already holds and reads again: the batched read has no way to be told a
    node is in hand.
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


async def read_template_components(
    db: InfrahubDatabase, branch: Branch, schema: MainSchemaTypes, template: CoreObjectTemplate, fields: list
) -> list[TemplateComponent]:
    """The tree of subtemplates under this template, read one level at a time.

    The subtemplates a level names are all known before any of them is read, so a level is read once
    for every parent it hangs from rather than once per parent. Reading a level names the level
    below it, which is what the next turn of the loop reads. `template` itself was read that way by
    the caller, which is why the walk starts with a level already in memory.
    """
    # The walk starts at the template itself; the components it names are what is returned.
    components: list[TemplateComponent] = []
    level = [_SubtemplateParent(schema=schema, template=template, components=components)]

    while level:
        next_level: list[_SubtemplateParent] = []
        level_components: list[TemplateComponent] = []
        for parent in level:
            subtemplates = await get_component_subtemplates(
                db=db, schema=parent.schema, template=parent.template, fields=fields
            )
            for subtemplate in subtemplates:
                # We retrieve peer schema for each peer in case we are processing a relationship which is based on a generic
                component = TemplateComponent(
                    subtemplate=subtemplate,
                    schema=registry.schema.get_node_schema(
                        name=subtemplate.get_schema().kind.removeprefix("Template"), branch=branch, duplicate=False
                    ),
                )
                parent.components.append(component)
                level_components.append(component)
                next_level.append(
                    _SubtemplateParent(schema=component.schema, template=subtemplate, components=component.components)
                )

        if not level_components:
            break

        await read_subtemplates(
            db=db, branch=branch, subtemplates=[component.subtemplate for component in level_components]
        )
        level = next_level

    return components


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
        source_id = template_attr.source_id or template_peer.id
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

        rel_peers = []
        for relationship in relationships:
            # deeper templates are handled in the next level of recursion
            if await _peer_is_a_template(db=db, relationship=relationship):
                continue
            # The peer is already read, so an id would send the checks and the write back to the database.
            rel_peers.append({"id": relationship.get_peer_in_hand() or relationship.peer_id})

        # Only set the relationship data if there are actual peers to set
        if rel_peers:
            obj_peer_data[rel_name] = rel_peers

        if rel_manager.schema.kind == RelationshipKind.PROFILE:
            obj_peer_data[rel_name] = peer_ids

    return obj_peer_data


async def allocate_from_resource_pools(
    db: InfrahubDatabase,
    branch: Branch,
    obj: Node,
    template: CoreObjectTemplate,
    pool_applier: AttributePoolApplierInterface,
    at: Timestamp | None = None,
    user_id: str = SYSTEM_USER_ID,
) -> None:
    """Allocate resources from template's _from_resource_pool relationships to the object.

    Handles two cases:
    - Relationship pools (IP address/prefix): allocates a new node and sets it as the relationship peer
    - Attribute pools (Number): allocates a value and sets it on the attribute, within the object's division
      when the pool has an allocation scope, so every other field of the object must be set beforehand
    An IP pool is recorded as the source of the relationship. A number pool is not written to the
    attribute's source: it is derived from the reservation record the allocation leaves behind.
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
            if not AllocationScope.from_stored(
                value=pool.get_attribute("allocation_scope").value, pool=pool.get_id()
            ).is_empty:
                attribute = obj.get_attribute(name=original_name)
                attribute.from_pool = {"id": pool.get_id()}
                attribute.from_pool_presence = PayloadPresence.SET
                await pool_applier.apply(node=obj, attribute=attribute, allocate=True, user_id=user_id)
                continue
            # Number pool: allocate a value and set it on the attribute
            attr_schema = obj_schema.get_attribute(name=original_name)
            allocated_value = await pool.get_resource(  # type: ignore[attr-defined]
                db=db, branch=branch, identifier=obj.get_id(), attribute=attr_schema
            )  # type: ignore
            attribute = obj.get_attribute(name=original_name)
            attribute.value = allocated_value
            attribute.is_default = False
            # Naming the pool records which one accounts for the number; the value is already drawn.
            attribute.from_pool = {"id": pool.id}
            attribute.tracking_pool = TrackingPool(pool_id=pool.id, provenance=PoolRecordProvenance.ALLOCATED)
        elif original_name in obj_schema.relationship_names:
            # IP pool: allocate a node and set it as the relationship peer
            allocated_resource = await pool.get_resource(  # type: ignore[attr-defined]
                db=db, branch=branch, identifier=obj.get_id(), at=at, user_id=user_id
            )  # type: ignore
            NodeMutationContext.record_if_active(node=allocated_resource, action=MutationAction.CREATED)

            obj_rel_manager = obj.get_relationship(name=original_name)
            await obj_rel_manager.update(
                data=PeerWithRelationshipMetadata(peer=allocated_resource, source_id=pool.id), db=db
            )


async def _new_component_node(
    db: InfrahubDatabase,
    branch: Branch,
    component: TemplateComponent,
    fields: Mapping[str, Any],
    process_pools: bool,
    at: Timestamp | None = None,
) -> Node:
    """Build the unsaved object a subtemplate describes, with the uuid its component holds.

    Raises:
        ValidationError: When the fields are not valid for the kind of the component.

    """
    node = await Node.init(schema=component.schema, db=db, branch=branch, at=at)
    write_components = _build_node_write_components(
        db=db, branch=branch, schema_branch=db.schema.get_schema_branch(name=branch.name)
    )
    return await node.new_from_fields(
        db=db,
        fields=dict(fields),
        pool_applier=write_components.pool_applier,
        profiles_mandatory_field_getter=write_components.profiles_mandatory_field_getter,
        process_pools=process_pools,
        generated_id=component.object_id,
    )


async def create_component(
    db: InfrahubDatabase,
    branch: Branch,
    constraint_runner: NodeConstraintRunner,
    parent_obj: Node,
    parent_template: CoreObjectTemplate,
    component: TemplateComponent,
    pool_applier: AttributePoolApplierInterface,
    at: Timestamp | None = None,
    user_id: str = SYSTEM_USER_ID,
) -> Node:
    """Create the object a subtemplate describes, as a component of the object holding it."""
    obj_peer_data = await extract_peer_data(
        db=db,
        template_peer=component.subtemplate,
        obj_peer_schema=component.schema,
        parent_obj=parent_obj,
        current_template=parent_template,
    )

    obj_peer = await _new_component_node(
        db=db, branch=branch, component=component, fields=obj_peer_data, process_pools=True, at=at
    )
    await constraint_runner.check(
        node=obj_peer, field_filters=_with_pooled_attributes(node=obj_peer, fields=list(obj_peer_data))
    )

    await allocate_from_resource_pools(
        db=db,
        branch=branch,
        obj=obj_peer,
        template=component.subtemplate,
        pool_applier=pool_applier,
        at=at,
        user_id=user_id,
    )

    template_profile_ids = await get_profile_ids(db=db, obj=component.subtemplate)
    if template_profile_ids:
        node_profiles_applier = NodeProfilesApplier(
            db=db, branch=branch, profile_data_reader=ProfileDataReader(db=db, branch=branch)
        )
        await node_profiles_applier.apply_profiles(node=obj_peer)

    await obj_peer.save(db=db, user_id=user_id)
    NodeMutationContext.record_if_active(node=obj_peer, action=MutationAction.CREATED)
    return obj_peer


async def create_components(
    db: InfrahubDatabase,
    branch: Branch,
    constraint_runner: NodeConstraintRunner,
    parent_obj: Node,
    parent_template: CoreObjectTemplate,
    components: list[TemplateComponent],
    pool_applier: AttributePoolApplierInterface,
    at: Timestamp | None = None,
    user_id: str = SYSTEM_USER_ID,
) -> None:
    """Create the objects these subtemplates describe, depth first.

    A component and the components it holds are created one after the other. A resource pool serving
    more than one level hands its resources out in the order the components are created, so walking
    the tree in any other order would move the resources each component is given.

    The subtemplates were read before any of them is created, so this creates without reading.
    """
    for component in components:
        obj_peer = await create_component(
            db=db,
            branch=branch,
            constraint_runner=constraint_runner,
            parent_obj=parent_obj,
            parent_template=parent_template,
            component=component,
            pool_applier=pool_applier,
            at=at,
            user_id=user_id,
        )
        await create_components(
            db=db,
            branch=branch,
            constraint_runner=constraint_runner,
            parent_obj=obj_peer,
            parent_template=component.subtemplate,
            components=component.components,
            pool_applier=pool_applier,
            at=at,
            user_id=user_id,
        )


def _has_number_pool_attribute(schema: MainSchemaTypes) -> bool:
    return any(attribute.kind == "NumberPool" for attribute in schema.attributes)


async def _template_pools(
    db: InfrahubDatabase, template: CoreObjectTemplate, skipped_fields: Collection[str]
) -> dict[str, Node]:
    """Return the pool the template names for each field of the object, except for the fields in `skipped_fields`.

    The template was read with these relationships and their peers, so naming the pools costs no query.
    """
    pools: dict[str, Node] = {}
    for rel_name in template.get_schema().relationship_names:
        field_name = rel_name.removesuffix(RESOURCE_POOL_REL_SUFFIX)
        if not rel_name.endswith(RESOURCE_POOL_REL_SUFFIX) or field_name in skipped_fields:
            continue
        pool = await template.get_relationship(name=rel_name).get_peer(db=db)
        if pool is not None:
            pools[field_name] = pool
    return pools


async def _template_pool_lock_names(
    node: Node, pools: Mapping[str, Node], pool_applier: AttributePoolApplierInterface, user_id: str
) -> set[str]:
    """Return the locks the unsaved `node` takes to draw from `pools`, the pool its template names for each field.

    Raises:
        ValidationError: When the schema of the branch does not define an element of a pool's scope.
        NodeNotFoundError: When a relationship element of a pool's scope names a peer that does not exist.

    """
    schema = node.get_schema()
    lock_names: set[str] = set()
    for field_name, pool in pools.items():
        if field_name in schema.relationship_names:
            lock_names.add(ip_pool_lock_name(pool_id=pool.get_id()))
            continue
        if field_name not in schema.attribute_names:
            continue
        attribute = node.get_attribute(name=field_name)
        if attribute.from_pool:
            # An object names a scoped pool on the attribute itself, so its own lock names hold this one.
            continue
        if AllocationScope.from_stored(value=pool.get_attribute("allocation_scope").value, pool=pool.get_id()).is_empty:
            lock_names.add(picking_lock_name(pool_id=pool.get_id(), division_key=None))
            continue
        attribute.from_pool = {"id": pool.get_id()}
        attribute.from_pool_presence = PayloadPresence.SET
        await pool_applier.apply(node=node, attribute=attribute, allocate=False, user_id=user_id)
        lock_names.add(picking_lock_name(pool_id=pool.get_id(), division_key=attribute.from_pool.get("division")))
    return lock_names


@dataclass
class _ComponentPreview:
    """An unsaved object built from a subtemplate as the component will be, and the pools the subtemplate names."""

    node: Node
    pools: dict[str, Node]


async def _component_previews(
    db: InfrahubDatabase,
    branch: Branch,
    parent_obj: Node,
    parent_template: CoreObjectTemplate,
    components: list[TemplateComponent],
    pooled_subtemplate_ids: set[str],
) -> list[_ComponentPreview]:
    """Return a preview of each component that draws from a pool, and of each component holding one that does.

    A preview draws nothing: it holds the fields its division of a scoped number pool is read from, and it stands
    for the parent of the components below it.
    """
    previews: list[_ComponentPreview] = []
    for component in components:
        if component.subtemplate.get_id() not in pooled_subtemplate_ids:
            continue
        obj_peer_data = await extract_peer_data(
            db=db,
            template_peer=component.subtemplate,
            obj_peer_schema=component.schema,
            parent_obj=parent_obj,
            current_template=parent_template,
        )
        node = await _new_component_node(
            db=db, branch=branch, component=component, fields=obj_peer_data, process_pools=False
        )
        previews.append(
            _ComponentPreview(
                node=node,
                pools=await _template_pools(db=db, template=component.subtemplate, skipped_fields=()),
            )
        )
        previews.extend(
            await _component_previews(
                db=db,
                branch=branch,
                parent_obj=node,
                parent_template=component.subtemplate,
                components=component.components,
                pooled_subtemplate_ids=pooled_subtemplate_ids,
            )
        )
    return previews


async def _pooled_subtemplate_ids(db: InfrahubDatabase, components: list[TemplateComponent]) -> set[str]:
    """Return the id of each subtemplate whose component draws from a pool, or holds a component that does."""
    pooled: set[str] = set()
    for component in components:
        below = await _pooled_subtemplate_ids(db=db, components=component.components)
        if (
            below
            or _has_number_pool_attribute(schema=component.schema)
            or await _template_pools(db=db, template=component.subtemplate, skipped_fields=())
        ):
            pooled.add(component.subtemplate.get_id())
        pooled |= below
    return pooled


async def get_template_pool_lock_names(
    db: InfrahubDatabase,
    branch: Branch,
    obj: Node,
    template: CoreObjectTemplate,
    components: list[TemplateComponent],
    user_fields: Collection[str],
    pool_applier: AttributePoolApplierInterface,
    user_id: str = SYSTEM_USER_ID,
) -> set[str]:
    """Return the pool locks a create from a template asks for beyond those of the object's own fields.

    `obj` is the unsaved preview of the object created from `template`, and `user_fields` names the fields the
    payload sets, which the template leaves alone. The locks are those of the pools the template names for the
    object without a scope, and of every pool its components draw from.

    Raises:
        ValidationError: When the schema of the branch does not define an element of a pool's scope.
        NodeNotFoundError: When a relationship element of a pool's scope names a peer that does not exist.

    """
    lock_names = await _template_pool_lock_names(
        node=obj,
        pools=await _template_pools(db=db, template=template, skipped_fields=user_fields),
        pool_applier=pool_applier,
        user_id=user_id,
    )
    previews = await _component_previews(
        db=db,
        branch=branch,
        parent_obj=obj,
        parent_template=template,
        components=components,
        pooled_subtemplate_ids=await _pooled_subtemplate_ids(db=db, components=components),
    )
    for preview in previews:
        lock_names |= await _template_pool_lock_names(
            node=preview.node, pools=preview.pools, pool_applier=pool_applier, user_id=user_id
        )
        lock_names |= get_pool_lock_names(node=preview.node)
    return lock_names


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


def _with_pooled_attributes(node: Node, fields: list[str]) -> list[str]:
    """Return `fields` plus every attribute of the new `node` a number pool filled.

    A NumberPool attribute is filled without the payload naming it, and a pool does not know which numbers objects
    hold outside its records, so the uniqueness check must see that number.
    """
    if not fields:
        # No filter already checks every constraint, and naming one field would narrow it.
        return fields
    pooled = [
        name
        for name in node.get_schema().attribute_names
        if name not in fields and node.get_attribute(name=name).tracking_pool is not None
    ]
    return fields + pooled


@dataclass(frozen=True)
class _NodeWriteComponents:
    pool_applier: AttributePoolApplier
    profiles_mandatory_field_getter: ProfilesMandatoryFieldGetter


def _build_node_write_components(
    db: InfrahubDatabase, branch: Branch, schema_branch: SchemaBranch
) -> _NodeWriteComponents:
    """Build the components that write one node, reading the node's profiles through one reader."""
    profile_data_reader = ProfileDataReader(db=db, branch=branch)
    return _NodeWriteComponents(
        pool_applier=build_attribute_pool_applier(
            profiles_applier=NodeProfilesApplier(db=db, branch=branch, profile_data_reader=profile_data_reader),
            db=db,
            schema_branch=schema_branch,
        ),
        profiles_mandatory_field_getter=ProfilesMandatoryFieldGetter(
            db=db, branch=branch, profile_data_reader=profile_data_reader
        ),
    )


async def _do_create_node(
    node_class: type[Node],
    node_constraint_runner: NodeConstraintRunner,
    pool_applier: AttributePoolApplierInterface,
    profiles_mandatory_field_getter: ProfilesMandatoryFieldGetter,
    mutation_context: NodeMutationContext,
    db: InfrahubDatabase,
    schema: NonGenericSchemaTypes,
    branch: Branch,
    fields_to_validate: list[str],
    data: dict[str, Any],
    object_template: CoreObjectTemplate | None,
    template_components: list[TemplateComponent],
    generated_id: str | None,
    at: Timestamp | None = None,
    user_id: str = SYSTEM_USER_ID,
) -> Node:
    with mutation_context:
        obj = await node_class.init(db=db, schema=schema, branch=branch)
        obj._object_template = object_template
        await obj.new_from_fields(
            db=db,
            fields=data,
            pool_applier=pool_applier,
            profiles_mandatory_field_getter=profiles_mandatory_field_getter,
            user_id=user_id,
            generated_id=generated_id,
        )
        await node_constraint_runner.check(
            node=obj, field_filters=_with_pooled_attributes(node=obj, fields=fields_to_validate)
        )
        await obj.save(db=db, at=at, user_id=user_id)

        if object_template:
            await create_components(
                db=db,
                branch=branch,
                constraint_runner=node_constraint_runner,
                parent_obj=obj,
                parent_template=object_template,
                components=template_components,
                pool_applier=pool_applier,
                at=at,
                user_id=user_id,
            )

    obj._mutation_context = mutation_context
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

    # A node created in a transaction this function opens draws its numbers through that transaction, so it
    # gets components of its own.
    schema_branch = db.schema.get_schema_branch(name=branch.name)
    components = _build_node_write_components(db=db, branch=branch, schema_branch=schema_branch)
    # The preview and the node created under the lock share one uuid, so the lock names hold the uuid of the node.
    generated_id = None if data.get("id") else str(UUIDT())
    preview_obj = await node_class.init(db=db, schema=schema, branch=branch)
    await preview_obj.new_from_fields(
        db=db,
        fields=data,
        pool_applier=components.pool_applier,
        profiles_mandatory_field_getter=components.profiles_mandatory_field_getter,
        process_pools=False,
        generated_id=generated_id,
    )
    lock_names = get_lock_names_on_object_mutation(node=preview_obj, schema_branch=schema_branch)
    # The preview read the object template to work out the lock names; the node created under the
    # lock is built from that same template rather than reading it again.
    object_template = preview_obj._object_template
    template_components: list[TemplateComponent] = []
    if object_template is not None:
        template_components = await read_template_components(
            db=db, branch=branch, schema=schema, template=object_template, fields=fields_to_validate
        )
        # Waiting for a pool's lock inside the transaction can leave this write and another allocation from the
        # pool waiting on each other.
        component_lock_names = await get_template_pool_lock_names(
            db=db,
            branch=branch,
            obj=preview_obj,
            template=object_template,
            components=template_components,
            user_fields=fields_to_validate,
            pool_applier=components.pool_applier,
            user_id=user_id,
        )
        lock_names = sorted({*lock_names, *component_lock_names})

    obj: Node
    mutation_context = NodeMutationContext()
    async with InfrahubMultiLock(lock_registry=lock.registry, locks=lock_names, metrics=False):
        if db.is_transaction:
            node_constraint_runner = await component_registry.get_component(NodeConstraintRunner, db=db, branch=branch)

            obj = await _do_create_node(
                node_class=node_class,
                node_constraint_runner=node_constraint_runner,
                pool_applier=components.pool_applier,
                profiles_mandatory_field_getter=components.profiles_mandatory_field_getter,
                mutation_context=mutation_context,
                db=db,
                schema=schema,
                branch=branch,
                fields_to_validate=fields_to_validate,
                data=data,
                at=at,
                user_id=user_id,
                object_template=object_template,
                template_components=template_components,
                generated_id=generated_id,
            )
        else:
            async with db.start_transaction() as dbt:
                node_constraint_runner = await component_registry.get_component(
                    NodeConstraintRunner, db=dbt, branch=branch
                )
                transaction_components = _build_node_write_components(
                    db=dbt, branch=branch, schema_branch=schema_branch
                )

                obj = await _do_create_node(
                    node_class=node_class,
                    node_constraint_runner=node_constraint_runner,
                    pool_applier=transaction_components.pool_applier,
                    profiles_mandatory_field_getter=transaction_components.profiles_mandatory_field_getter,
                    mutation_context=mutation_context,
                    db=dbt,
                    schema=schema,
                    branch=branch,
                    fields_to_validate=fields_to_validate,
                    data=data,
                    at=at,
                    user_id=user_id,
                    object_template=object_template,
                    template_components=template_components,
                    generated_id=generated_id,
                )

    # The node was written from its in-memory state, so the profiles it is linked to are the ones
    # its payload or its template set on it; there is nothing to read back.
    if _has_profiles_set(node=obj):
        node_profiles_applier = NodeProfilesApplier(
            db=db, branch=branch, profile_data_reader=ProfileDataReader(db=db, branch=branch)
        )
        await node_profiles_applier.apply_profiles(node=obj)
        await obj.save(db=db, user_id=user_id)

    return obj
