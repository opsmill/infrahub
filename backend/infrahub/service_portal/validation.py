from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub.core.account import ObjectPermission
from infrahub.core.constants import (
    OBJECT_TEMPLATE_RELATIONSHIP_NAME,
    InfrahubKind,
    PermissionAction,
    PermissionDecision,
    RelationshipCardinality,
)
from infrahub.core.constants.schema import RESOURCE_POOL_REL_SUFFIX
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreObjectTemplate
from infrahub.core.schema import NodeSchema
from infrahub.exceptions import SchemaNotFoundError, ValidationError
from infrahub.service_portal.constants import ServiceCatalogEntryMode

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.protocols import CoreServiceCatalogEntry
    from infrahub.database import InfrahubDatabase


@dataclass(frozen=True)
class _PeerReference:
    key: str
    node_id: str
    kind: str
    """Kind the referenced node must be, or inherit from."""


def get_entry_mode(entry: CoreServiceCatalogEntry) -> ServiceCatalogEntryMode:
    return ServiceCatalogEntryMode(entry.mode.value.value)


def get_target_schema(db: InfrahubDatabase, entry: CoreServiceCatalogEntry, branch: Branch) -> NodeSchema | None:
    """Return the node schema of the entry's target kind, or None when it isn't a node on this branch."""
    try:
        schema = db.schema.get(name=entry.target_kind.value, branch=branch, duplicate=False)
    except SchemaNotFoundError:
        return None
    return schema if isinstance(schema, NodeSchema) else None


def get_request_permission(target_schema: NodeSchema) -> ObjectPermission:
    """Return the permission a requester needs: creating the target kind on a branch other than the default one."""
    return ObjectPermission(
        namespace=target_schema.namespace,
        name=target_schema.name,
        action=PermissionAction.CREATE.value,
        decision=PermissionDecision.ALLOW_OTHER.value,
    )


async def validate_request_inputs(
    db: InfrahubDatabase,
    branch: Branch,
    entry: CoreServiceCatalogEntry,
    target_schema: NodeSchema,
    inputs: Any,
) -> None:
    """Check submitted inputs against the entry's allowlist and the target kind's create input.

    Uniqueness clashes and exhausted pools are left to the workflow that creates the object.

    Raises:
        ValidationError: Keyed by the first offending input key.

    """
    if not isinstance(inputs, dict):
        raise ValidationError({"inputs": "The inputs must be an object keyed by field name"})

    allowlist: list[str] = entry.fields.value or []
    references: list[_PeerReference] = []
    for key, value in inputs.items():
        name = key.removesuffix(RESOURCE_POOL_REL_SUFFIX)
        if name == OBJECT_TEMPLATE_RELATIONSHIP_NAME:
            raise ValidationError({key: "The object template is set by the service and can't be submitted"})
        if name not in allowlist:
            raise ValidationError({key: f"{key} is not a field of this service"})
        references.extend(_check_field(target_schema=target_schema, key=key, name=name, value=value))

    await _check_required_fields(db=db, entry=entry, target_schema=target_schema, inputs=inputs)
    await _check_references(db=db, branch=branch, references=references)


def _check_field(target_schema: NodeSchema, key: str, name: str, value: Any) -> list[_PeerReference]:
    if key != name:
        if name not in target_schema.attribute_names and name not in target_schema.relationship_names:
            raise ValidationError({key: f"{name} is not a field of {target_schema.kind}"})
        return [_pool_reference(key=key, data=value)]

    if name in target_schema.attribute_names:
        if not isinstance(value, dict):
            raise ValidationError({key: 'The value must be an object like {"value": ...}'})
        if "from_pool" in value:
            return [_pool_reference(key=key, data=value["from_pool"])]
        attribute_schema = target_schema.get_attribute(name=name)
        attribute_schema.get_class().validate(value=value.get("value"), name=key, schema=attribute_schema)
        return []

    if name in target_schema.relationship_names:
        relationship_schema = target_schema.get_relationship(name=name)
        if relationship_schema.cardinality == RelationshipCardinality.MANY:
            if not isinstance(value, list):
                raise ValidationError({key: 'The value must be a list like [{"id": ...}]'})
            return [_peer_reference(key=key, data=item, kind=relationship_schema.peer) for item in value]
        if isinstance(value, dict) and "from_pool" in value:
            return [_pool_reference(key=key, data=value["from_pool"])]
        return [_peer_reference(key=key, data=value, kind=relationship_schema.peer)]

    raise ValidationError({key: f"{name} is not a field of {target_schema.kind}"})


def _peer_reference(key: str, data: Any, kind: str) -> _PeerReference:
    if not isinstance(data, dict) or not isinstance(data.get("id"), str):
        raise ValidationError({key: 'The value must reference an object like {"id": ...}'})
    return _PeerReference(key=key, node_id=data["id"], kind=kind)


def _pool_reference(key: str, data: Any) -> _PeerReference:
    if not isinstance(data, dict) or not isinstance(data.get("id"), str):
        raise ValidationError({key: 'The value must reference a resource pool like {"id": ...}'})
    return _PeerReference(key=key, node_id=data["id"], kind=InfrahubKind.RESOURCEPOOL)


async def _check_required_fields(
    db: InfrahubDatabase,
    entry: CoreServiceCatalogEntry,
    target_schema: NodeSchema,
    inputs: dict[str, Any],
) -> None:
    missing = [
        name
        for name in entry.fields.value or []
        if name not in inputs
        and f"{name}{RESOURCE_POOL_REL_SUFFIX}" not in inputs
        and _is_required(target_schema=target_schema, name=name)
    ]
    if not missing:
        return

    template = await entry.template.get_peer(db=db, peer_type=CoreObjectTemplate)
    for name in missing:
        if template is None or not await _template_sets(db=db, template=template, name=name):
            raise ValidationError({name: f"A value must be provided for {name}"})


def _is_required(target_schema: NodeSchema, name: str) -> bool:
    if name in target_schema.attribute_names:
        attribute_schema = target_schema.get_attribute(name=name)
        return not attribute_schema.optional and attribute_schema.default_value is None
    if name in target_schema.relationship_names:
        return not target_schema.get_relationship(name=name).optional
    return False


async def _template_sets(db: InfrahubDatabase, template: CoreObjectTemplate, name: str) -> bool:
    template_schema = template.get_schema()
    if name in template_schema.attribute_names and template.get_attribute(name=name).value is not None:
        return True
    for relationship_name in (name, f"{name}{RESOURCE_POOL_REL_SUFFIX}"):
        if relationship_name in template_schema.relationship_names and await template.get_relationship(
            name=relationship_name
        ).get_relationships(db=db):
            return True
    return False


async def _check_references(db: InfrahubDatabase, branch: Branch, references: list[_PeerReference]) -> None:
    if not references:
        return
    nodes = await NodeManager.get_many(db=db, ids=list({ref.node_id for ref in references}), branch=branch)
    for ref in references:
        node = nodes.get(ref.node_id)
        if node is None or not _is_kind(node=node, kind=ref.kind):
            raise ValidationError({ref.key: f"{ref.node_id} is not a {ref.kind}"})


def _is_kind(node: Node, kind: str) -> bool:
    return node.get_kind() == kind or kind in node.get_schema().inherit_from
