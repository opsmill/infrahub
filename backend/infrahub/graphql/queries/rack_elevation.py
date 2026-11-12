from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import Boolean, Enum, Field, Int, List, NonNull, ObjectType, String

from infrahub.rack_elevation.models import RackFace, RackItemSnapshot, RackRole
from infrahub.rack_elevation.models import RackItemPlacement as RackItemPlacementModel
from infrahub.rack_elevation.placement import compute_totals, order_items
from infrahub.rack_elevation.presentation import ItemPresentation, RackItemPresenter
from infrahub.rack_elevation.provider import build_rack_elevation_provider

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.graphql.initialization import GraphqlContext


class RackElevationRoleType(Enum):
    class Meta:
        name = "RackElevationRole"
        enum = RackRole
        description = "The part a kind plays in rack elevations."


class RackFaceType(Enum):
    class Meta:
        name = "RackFace"
        enum = RackFace


class RackItemPlacementType(Enum):
    class Meta:
        name = "RackItemPlacement"
        enum = RackItemPlacementModel


class RackElevationKind(ObjectType):
    kind = String(required=True)
    role = Field(RackElevationRoleType, required=True)


class RackElevationRack(ObjectType):
    id = String(required=True)
    kind = String(required=True)
    display_label = String(required=True)
    u_height = Int(required=True)
    used_units = Int(required=True)
    utilization = Int(required=True, description="Percent of the units in use, rounded down.")
    total_weight = Int(description="Weight in kg of every item in the rack. Null when no item has a weight.")


class RackElevationItem(ObjectType):
    id = String(required=True)
    kind = String(required=True)
    display_label = String(required=True)
    label = String(required=True, description="Value of label_by, or display_label.")
    color = String(description="Hex color of the color_by dropdown choice, or null.")
    type_id = String()
    type_display_label = String()
    placement = Field(RackItemPlacementType, required=True)
    position = Int(description="Lowest unit the item uses. Null unless the item is mounted.")
    face = Field(RackFaceType, description="Null unless the item is mounted.")
    u_height = Int(required=True, description="Height from the type. 0 for a 0U type.")
    full_depth = Boolean(required=True)
    weight = Int(description="Weight in kg, from the type.")


class RackElevation(ObjectType):
    rack = Field(RackElevationRack, required=True)
    items = Field(
        List(NonNull(RackElevationItem)),
        required=True,
        description="Ordered by position descending, then unpositioned items, then 0U items.",
    )


def build_item_payload(item: RackItemSnapshot, presentation: ItemPresentation) -> dict[str, Any]:
    return {
        "id": item.id,
        "kind": item.kind,
        "display_label": item.display_label,
        "label": presentation.label,
        "color": presentation.color,
        "type_id": item.type_id,
        "type_display_label": item.type_display_label,
        "placement": item.placement,
        "position": item.position,
        "face": item.face,
        "u_height": item.u_height,
        "full_depth": item.full_depth,
        "weight": item.weight,
    }


class RackElevationKindsQuery:
    @staticmethod
    async def resolve(root: dict, info: GraphQLResolveInfo) -> list[dict[str, Any]]:  # noqa: ARG004
        graphql_context: GraphqlContext = info.context

        async with graphql_context.db.start_session(read_only=True) as db:
            provider = build_rack_elevation_provider(db=db, branch=graphql_context.branch, at=graphql_context.at)
            entries = provider.list_kinds()

        return [{"kind": entry.kind, "role": entry.role} for entry in entries]


class RackElevationQuery:
    @staticmethod
    async def resolve(
        root: dict,  # noqa: ARG004
        info: GraphQLResolveInfo,
        rack: str,
        label_by: str | None = None,
        color_by: str | None = None,
    ) -> dict[str, Any]:
        graphql_context: GraphqlContext = info.context

        async with graphql_context.db.start_session(read_only=True) as db:
            provider = build_rack_elevation_provider(db=db, branch=graphql_context.branch, at=graphql_context.at)
            rack_snapshot, items = await provider.load_rack(rack_id=rack)
            totals = compute_totals(rack=rack_snapshot, items=items)
            ordered_items = order_items(items)
            presenter = RackItemPresenter(db=db, branch=graphql_context.branch, at=graphql_context.at)
            presentations = await presenter.present(items=ordered_items, label_by=label_by, color_by=color_by)

        return {
            "rack": {
                "id": rack_snapshot.id,
                "kind": rack_snapshot.kind,
                "display_label": rack_snapshot.display_label,
                "u_height": rack_snapshot.u_height,
                "used_units": totals.used_units,
                "utilization": totals.utilization,
                "total_weight": totals.total_weight,
            },
            "items": [build_item_payload(item=item, presentation=presentations[item.id]) for item in ordered_items],
        }


InfrahubRackElevationKinds = Field(
    List(NonNull(RackElevationKind)),
    resolver=RackElevationKindsQuery.resolve,
    required=True,
    description="Kinds that take part in rack elevations, with the role each one plays.",
)

InfrahubRackElevation = Field(
    RackElevation,
    rack=String(required=True),
    label_by=String(required=False),
    color_by=String(required=False),
    resolver=RackElevationQuery.resolve,
    required=True,
    description="The items of a rack, their position, and the rack totals.",
)
