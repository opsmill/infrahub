from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import Field, Int, List, NonNull, ObjectType, String

from infrahub.core.manager import NodeManager
from infrahub.core.protocols import BuiltinTag, CoreServiceCatalogEntry
from infrahub.core.registry import registry
from infrahub.service_portal.constants import ServiceCatalogEntryMode
from infrahub.service_portal.validation import get_entry_mode, get_request_permission, get_target_schema

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.graphql.initialization import GraphqlContext


class ServiceCatalogEntryInfo(ObjectType):
    id = Field(String, required=True, description="ID of the catalog entry")
    name = Field(String, required=True, description="Name of the service")
    description = Field(String, required=False, description="Short explanation of the service")
    icon = Field(String, required=False, description="Icon of the service, as an mdi: icon name")
    tags = Field(List(of_type=NonNull(String)), required=True, description="Names of the tags of the service")
    target_kind = Field(String, required=True, description="Kind of the service object created by a request")
    mode = Field(String, required=True, description="How a request is fulfilled: review or direct")
    fields = Field(
        List(of_type=NonNull(String)),
        required=True,
        description="Attribute and relationship names of the target kind shown on the order form, in form order",
    )
    generators = Field(
        List(of_type=NonNull(String)),
        required=True,
        description="Names of the generator definitions run on the service object, in run order",
    )
    template_id = Field(String, required=False, description="ID of the object template applied to the service object")


class ServiceCatalog(ObjectType):
    count = Field(Int, required=True, description="Number of services the caller can request")
    entries = Field(
        List(of_type=NonNull(ServiceCatalogEntryInfo)), required=True, description="Services the caller can request"
    )


async def resolve_service_catalog(
    root: dict,  # noqa: ARG001
    info: GraphQLResolveInfo,
) -> dict[str, Any]:
    graphql_context: GraphqlContext = info.context
    db = graphql_context.db
    permissions = graphql_context.active_permissions
    # The catalog is published on the default branch, whatever branch the request is sent on
    branch = registry.get_branch_from_registry()

    entries = await NodeManager.query(db=db, schema=CoreServiceCatalogEntry, branch=branch, prefetch_relationships=True)

    available: list[dict[str, Any]] = []
    for entry in entries:
        mode = get_entry_mode(entry)
        if mode != ServiceCatalogEntryMode.REVIEW:
            continue  # STUB(Phase 7): direct mode
        target_schema = get_target_schema(db=db, entry=entry, branch=branch)
        if target_schema is None or not permissions.has_permission(permission=get_request_permission(target_schema)):
            continue
        # STUB(Phase 6): every entry is treated as available, no validation nor include_unavailable yet
        tags = [await rel.get_peer(db=db, peer_type=BuiltinTag) for rel in await entry.tags.get_relationships(db=db)]
        available.append(
            {
                "id": entry.id,
                "name": entry.name.value,
                "description": entry.description.value,
                "icon": entry.icon.value,
                "tags": sorted(tag.name.value for tag in tags),
                "target_kind": target_schema.kind,
                "mode": mode.value,
                "fields": entry.fields.value or [],
                "generators": entry.generators.value or [],
                "template_id": await entry.template.get_peer_id(db=db),
            }
        )

    return {"count": len(available), "entries": available}


InfrahubServiceCatalog = Field(
    ServiceCatalog,
    description="List the Service Portal services the caller can request.",
    resolver=resolve_service_catalog,
    required=True,
)
