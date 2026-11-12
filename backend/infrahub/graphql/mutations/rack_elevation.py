from __future__ import annotations

from typing import TYPE_CHECKING, Self

from graphene import Boolean, Field, Int, Mutation, String

from infrahub.core.account import GlobalPermission, ObjectPermission
from infrahub.core.constants import PermissionAction, PermissionDecision
from infrahub.graphql.queries.rack_elevation import RackElevationItem, RackFaceType, build_item_payload
from infrahub.permissions import get_global_permission_for_kind
from infrahub.rack_elevation.presentation import ItemPresentation
from infrahub.rack_elevation.provider import build_rack_elevation_provider

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.graphql.initialization import GraphqlContext
    from infrahub.rack_elevation.models import RackFace


class RackElevationPlace(Mutation):
    class Meta:
        name = "RackElevationPlaceResult"
        description = "Move an item into a rack at a unit and face, or keep it in the rack without a unit."

    ok = Boolean(required=True)
    item = Field(RackElevationItem, required=True)

    class Arguments:
        item = String(required=True)
        rack = String(required=True)
        position = Int(required=False)
        face = RackFaceType(required=False)

    @classmethod
    async def mutate(
        cls,
        root: dict,  # noqa: ARG003
        info: GraphQLResolveInfo,
        item: str,
        rack: str,
        position: int | None = None,
        face: RackFace | None = None,
    ) -> Self:
        graphql_context: GraphqlContext = info.context
        provider = build_rack_elevation_provider(
            db=graphql_context.db, branch=graphql_context.branch, at=graphql_context.at
        )

        current = await provider.load_item(item_id=item)
        cls._validate_permissions(graphql_context=graphql_context, kind=current.kind)

        placed = await provider.place(item_id=item, rack_id=rack, position=position, face=face)

        return cls(
            ok=True,
            item=build_item_payload(item=placed, presentation=ItemPresentation(label=placed.display_label, color=None)),
        )

    @staticmethod
    def _validate_permissions(graphql_context: GraphqlContext, kind: str) -> None:
        if not graphql_context.account_session:
            return
        schema = graphql_context.db.schema.get(name=kind, branch=graphql_context.branch)
        decision = (
            PermissionDecision.ALLOW_DEFAULT.value
            if graphql_context.branch.is_default
            else PermissionDecision.ALLOW_OTHER.value
        )
        global_action = get_global_permission_for_kind(schema=schema)
        permission: GlobalPermission | ObjectPermission
        if global_action:
            permission = GlobalPermission(action=global_action, decision=decision)
        else:
            permission = ObjectPermission(
                namespace=schema.namespace,
                name=schema.name,
                action=PermissionAction.UPDATE.value,
                decision=decision,
            )
        graphql_context.active_permissions.raise_for_permissions(permissions=[permission])
