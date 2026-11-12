from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants import RelationshipCardinality, SchemaElementPathType
from infrahub.core.schema.rack_elevation_schema import (
    RackElevationMountableMapping,
    RackElevationMountableTypeMapping,
    RackElevationRackMapping,
)
from infrahub.rack_elevation.constants import RackTotalAttribute
from infrahub.rack_elevation.mapped.mapping import is_calculated_total
from infrahub.rack_elevation.models import RackFace, RackRole

from .interface import SchemaBranchValidator

if TYPE_CHECKING:
    from infrahub.core.schema import AttributeSchema, MainSchemaTypes
    from infrahub.core.schema.rack_elevation_schema import RackElevationSchema
    from infrahub.core.schema.schema_branch import SchemaBranch

NUMBER_KIND = "Number"
BOOLEAN_KIND = "Boolean"
DROPDOWN_KIND = "Dropdown"
VALUE_PROPERTY = "value"


class RackElevationValidator(SchemaBranchValidator):
    """Checks that every `rack_elevation` mapping points to attributes and relationships that exist."""

    def check(self, schema_branch: SchemaBranch) -> None:
        for name in schema_branch.all_names:
            schema = schema_branch.get(name=name, duplicate=False)
            mapping = schema.rack_elevation
            if mapping is None:
                continue
            if isinstance(mapping, RackElevationRackMapping):
                self._check_rack(schema_branch=schema_branch, schema=schema, mapping=mapping)
            elif isinstance(mapping, RackElevationMountableTypeMapping):
                self._check_mountable_type(schema_branch=schema_branch, schema=schema, mapping=mapping)
            else:
                self._check_mountable(schema_branch=schema_branch, schema=schema, mapping=mapping)

    def _check_rack(
        self, schema_branch: SchemaBranch, schema: MainSchemaTypes, mapping: RackElevationRackMapping
    ) -> None:
        self._check_attribute(
            schema_branch=schema_branch, schema=schema, key="u_height", path=mapping.u_height, expected_kind=NUMBER_KIND
        )
        for attribute in schema.attributes:
            if attribute.name in RackTotalAttribute.available_types() and not is_calculated_total(attribute):
                raise ValueError(
                    f"{schema.kind}.rack_elevation: attribute '{attribute.name}' is calculated by Infrahub "
                    "on a rack kind and cannot be declared"
                )

    def _check_mountable_type(
        self, schema_branch: SchemaBranch, schema: MainSchemaTypes, mapping: RackElevationMountableTypeMapping
    ) -> None:
        self._check_attribute(
            schema_branch=schema_branch, schema=schema, key="u_height", path=mapping.u_height, expected_kind=NUMBER_KIND
        )
        self._check_attribute(
            schema_branch=schema_branch,
            schema=schema,
            key="full_depth",
            path=mapping.full_depth,
            expected_kind=BOOLEAN_KIND,
        )
        if mapping.weight is not None:
            self._check_attribute(
                schema_branch=schema_branch, schema=schema, key="weight", path=mapping.weight, expected_kind=NUMBER_KIND
            )

    def _check_mountable(
        self, schema_branch: SchemaBranch, schema: MainSchemaTypes, mapping: RackElevationMountableMapping
    ) -> None:
        self._check_attribute(
            schema_branch=schema_branch,
            schema=schema,
            key="position",
            path=mapping.position,
            expected_kind=NUMBER_KIND,
        )
        face = self._check_attribute(
            schema_branch=schema_branch, schema=schema, key="face", path=mapping.face, expected_kind=DROPDOWN_KIND
        )
        choice_names = {choice.name for choice in face.choices or []}
        face_values = RackFace.available_types()
        if not set(face_values) <= choice_names:
            raise ValueError(
                f"{schema.kind}.rack_elevation.face: dropdown '{face.name}' must have the choices "
                f"{', '.join(face_values)}"
            )
        self._check_relationship(
            schema_branch=schema_branch, schema=schema, key="rack", name=mapping.rack, peer_role=RackRole.RACK
        )
        if mapping.type is None:
            if schema.is_node_schema:
                raise ValueError(f"{schema.kind}.rack_elevation.type: a node must name its type relationship")
            return
        self._check_relationship(
            schema_branch=schema_branch,
            schema=schema,
            key="type",
            name=mapping.type,
            peer_role=RackRole.MOUNTABLE_TYPE,
        )

    @staticmethod
    def _check_attribute(
        schema_branch: SchemaBranch, schema: MainSchemaTypes, key: str, path: str, expected_kind: str
    ) -> AttributeSchema:
        schema_path = schema_branch.validate_schema_path(
            node_schema=schema,
            path=path,
            allowed_path_types=SchemaElementPathType.ATTR_WITH_PROP,
            element_name=f"rack_elevation.{key}",
        )
        attribute = schema_path.active_attribute_schema
        if schema_path.attribute_property_name != VALUE_PROPERTY:
            raise ValueError(f"{schema.kind}.rack_elevation.{key}: the path must end with '__{VALUE_PROPERTY}'")
        if attribute.kind != expected_kind:
            raise ValueError(
                f"{schema.kind}.rack_elevation.{key}: attribute '{attribute.name}' is a {attribute.kind}, "
                f"expected a {expected_kind}"
            )
        return attribute

    @staticmethod
    def _check_relationship(
        schema_branch: SchemaBranch, schema: MainSchemaTypes, key: str, name: str, peer_role: RackRole
    ) -> None:
        header = f"{schema.kind}.rack_elevation.{key}"
        if name not in schema.relationship_names:
            raise ValueError(f"{header}: relationship '{name}' does not exist")
        relationship = schema.get_relationship(name=name)
        if relationship.cardinality != RelationshipCardinality.ONE:
            raise ValueError(f"{header}: relationship '{name}' must have a cardinality of one")
        peer = schema_branch.get(name=relationship.peer, duplicate=False)
        if peer.is_node_schema or peer.rack_elevation is not None:
            peer_mapping: RackElevationSchema | None = peer.rack_elevation
            if peer_mapping is None or peer_mapping.role != peer_role:
                raise ValueError(
                    f"{header}: the peer '{peer.kind}' of relationship '{name}' must have the "
                    f"rack_elevation role '{peer_role.value}'"
                )
