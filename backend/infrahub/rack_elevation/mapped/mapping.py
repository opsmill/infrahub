from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from infrahub.core.constants import AllowOverrideType
from infrahub.core.schema.rack_elevation_schema import (
    RackElevationMountableMapping,
    RackElevationMountableTypeMapping,
    RackElevationRackMapping,
)
from infrahub.rack_elevation.constants import ATTRIBUTE_VALUE_PATH_SUFFIX, RackPlaceArgument, RackTotalAttribute
from infrahub.rack_elevation.models import RackElevationKindEntry, RackRole

if TYPE_CHECKING:
    from infrahub.core.schema import AttributeSchema, MainSchemaTypes
    from infrahub.core.schema.rack_elevation_schema import RackElevationSchema
    from infrahub.core.schema.schema_branch import SchemaBranch


def attribute_name(path: str) -> str:
    """Name of the attribute a mapping path points to: `height__value` gives `height`."""
    return path.removesuffix(ATTRIBUTE_VALUE_PATH_SUFFIX)


def get_mapping(schema_branch: SchemaBranch, kind: str) -> RackElevationSchema | None:
    return schema_branch.get(name=kind, duplicate=False).rack_elevation


def is_calculated_total(attribute: AttributeSchema) -> bool:
    """True for the read-only attributes Infrahub adds to a rack kind, false for one a customer declared."""
    return (
        attribute.name in RackTotalAttribute.available_types()
        and attribute.read_only
        and attribute.allow_override == AllowOverrideType.NONE
    )


class RackKindFields(BaseModel):
    model_config = ConfigDict(frozen=True)

    u_height: str


class MountableKindFields(BaseModel):
    model_config = ConfigDict(frozen=True)

    rack_relationship: str
    position_attribute: str
    face_attribute: str
    type_relationship: str

    def customer_field_name(self, argument: str) -> str:
        """The customer's name for a placement argument: `face` gives the face attribute, `rack` the relationship."""
        match argument:
            case RackPlaceArgument.POSITION:
                return self.position_attribute
            case RackPlaceArgument.FACE:
                return self.face_attribute
            case RackPlaceArgument.RACK:
                return self.rack_relationship
            case _:
                return argument


class TypeKindFields(BaseModel):
    model_config = ConfigDict(frozen=True)

    height_attribute: str
    depth_attribute: str
    weight_attribute: str | None


class RackMappingIndex(BaseModel):
    """The rack mappings of one schema branch, resolved to attribute and relationship names."""

    model_config = ConfigDict(frozen=True)

    kinds_by_role: dict[RackRole, list[str]]
    rack_fields: dict[str, RackKindFields]
    mountable_kinds: dict[str, MountableKindFields]
    type_kinds: dict[str, TypeKindFields]

    @classmethod
    def from_schema_branch(cls, schema_branch: SchemaBranch) -> RackMappingIndex:
        kinds_by_role: dict[RackRole, list[str]] = {role: [] for role in RackRole}
        rack_fields: dict[str, RackKindFields] = {}
        mountable_kinds: dict[str, MountableKindFields] = {}
        type_kinds: dict[str, TypeKindFields] = {}
        for name in schema_branch.all_names:
            schema = schema_branch.get(name=name, duplicate=False)
            mapping = schema.rack_elevation
            if mapping is None:
                continue
            kinds_by_role[RackRole(mapping.role)].append(schema.kind)
            _register_fields(
                schema=schema,
                mapping=mapping,
                rack_fields=rack_fields,
                mountable_kinds=mountable_kinds,
                type_kinds=type_kinds,
            )
        return cls(
            kinds_by_role=kinds_by_role, rack_fields=rack_fields, mountable_kinds=mountable_kinds, type_kinds=type_kinds
        )

    def list_kinds(self) -> list[RackElevationKindEntry]:
        return [
            RackElevationKindEntry(kind=kind, role=role) for role, kinds in self.kinds_by_role.items() for kind in kinds
        ]

    def type_fields(self, kind: str) -> TypeKindFields:
        return self.type_kinds[kind]


def _register_fields(
    schema: MainSchemaTypes,
    mapping: RackElevationSchema,
    rack_fields: dict[str, RackKindFields],
    mountable_kinds: dict[str, MountableKindFields],
    type_kinds: dict[str, TypeKindFields],
) -> None:
    if isinstance(mapping, RackElevationRackMapping):
        rack_fields[schema.kind] = RackKindFields(u_height=attribute_name(mapping.u_height))
    elif isinstance(mapping, RackElevationMountableTypeMapping):
        type_kinds[schema.kind] = TypeKindFields(
            height_attribute=attribute_name(mapping.u_height),
            depth_attribute=attribute_name(mapping.full_depth),
            weight_attribute=attribute_name(mapping.weight) if mapping.weight else None,
        )
    elif isinstance(mapping, RackElevationMountableMapping) and schema.is_node_schema and mapping.type:
        mountable_kinds[schema.kind] = MountableKindFields(
            rack_relationship=mapping.rack,
            position_attribute=attribute_name(mapping.position),
            face_attribute=attribute_name(mapping.face),
            type_relationship=mapping.type,
        )
