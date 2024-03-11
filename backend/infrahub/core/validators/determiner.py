from collections import defaultdict
from typing import Union

from infrahub_sdk.client import NodeDiff

from infrahub.core.constants import RelationshipKind, SchemaPathType
from infrahub.core.constants.schema import UpdateSupport
from infrahub.core.diff.model import DiffElementType
from infrahub.core.models import SchemaUpdateConstraintInfo
from infrahub.core.path import SchemaPath
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.schema.generic_schema import GenericSchema
from infrahub.core.schema.node_schema import NodeSchema
from infrahub.core.schema.relationship_schema import RelationshipSchema
from infrahub.core.schema_manager import SchemaBranch
from infrahub.core.validators import CONSTRAINT_VALIDATOR_MAP
from infrahub.log import get_logger

LOG = get_logger(__name__)


class ConstraintValidatorDeterminer:
    def __init__(self, schema_branch: SchemaBranch):
        self.schema_branch = schema_branch
        self._node_diffs_by_kind: dict[str, NodeDiff] = defaultdict(list)
        self._attribute_element_map: dict[str, dict[str, list[NodeDiff]]] = {}
        self._relationship_element_map: dict[str, dict[str, list[NodeDiff]]] = {}

    def _index_node_diffs(self, node_diffs: list[NodeDiff]) -> None:
        for node_diff in node_diffs:
            node_kind = node_diff["kind"]
            self._node_diffs_by_kind[node_kind].append(node_diff)
            if node_kind not in self._attribute_element_map:
                self._attribute_element_map[node_kind] = {}
            for element in node_diff["elements"]:
                element_name = element["name"]
                element_type = element["type"]
                if element_type.lower() in (
                    DiffElementType.RELATIONSHIP_MANY.value.lower(),
                    DiffElementType.RELATIONSHIP_ONE.value.lower(),
                ):
                    if node_kind not in self._relationship_element_map:
                        self._relationship_element_map[node_kind] = {}
                    if element_name not in self._relationship_element_map[node_kind]:
                        self._relationship_element_map[node_kind][element_name] = []
                    self._relationship_element_map[node_kind][node_kind].append(element)
                elif element_type.lower() in (DiffElementType.ATTRIBUTE.value.lower(),):
                    if node_kind not in self._attribute_element_map:
                        self._attribute_element_map[node_kind] = {}
                    if element_name not in self._attribute_element_map[node_kind]:
                        self._attribute_element_map[node_kind][element_name] = []
                    self._attribute_element_map[node_kind][node_kind].append(element)

    def _get_attribute_diffs(self, kind: str, name: str) -> list[NodeDiff]:
        return self._attribute_element_map.get(kind, {}).get(name, [])

    def _get_relationship_diffs(self, kind: str, name: str) -> list[NodeDiff]:
        return self._relationship_element_map.get(kind, {}).get(name, [])

    async def get_constraints(
        self, node_diffs: list[NodeDiff], filter_invalid: bool = True
    ) -> list[SchemaUpdateConstraintInfo]:
        self._index_node_diffs(node_diffs)
        constraints: list[SchemaUpdateConstraintInfo] = []

        for kind in self._node_diffs_by_kind.keys():
            schema = self.schema_branch.get(name=kind, duplicate=False)
            constraints.extend(await self._get_constraints_for_one_schema(schema))

        if not filter_invalid:
            return constraints

        validated_constraints: list[SchemaUpdateConstraintInfo] = []
        for constraint in constraints:
            if CONSTRAINT_VALIDATOR_MAP.get(constraint.constraint_name, None):
                validated_constraints.append(constraint)
            else:
                LOG.warning(
                    f"Unable to validate: {constraint.constraint_name!r} for {constraint.path.get_path()!r}, validator not available",
                    constraint_name=constraint.constraint_name,
                    path=constraint.path.get_path(),
                )

        return validated_constraints

    async def _get_constraints_for_one_schema(
        self, schema: Union[NodeSchema, GenericSchema]
    ) -> list[SchemaUpdateConstraintInfo]:
        constraints: list[SchemaUpdateConstraintInfo] = []
        constraints.extend(await self._get_property_constraints_for_one_schema(schema=schema))
        constraints.extend(await self._get_attribute_constraints_for_one_schema(schema=schema))
        constraints.extend(await self._get_relationship_constraints_for_one_schema(schema=schema))
        return constraints

    async def _get_property_constraints_for_one_schema(
        self, schema: Union[NodeSchema, GenericSchema]
    ) -> list[SchemaUpdateConstraintInfo]:
        constraints: list[SchemaUpdateConstraintInfo] = []
        for prop_name, prop_field_info in schema.model_fields.items():
            if prop_name in ["attributes", "relationships"] or not prop_field_info.json_schema_extra or not isinstance(prop_field_info.json_schema_extra, dict):
                continue

            prop_field_update = prop_field_info.json_schema_extra.get("update")
            if prop_field_update != UpdateSupport.VALIDATE_CONSTRAINT.value:
                continue

            if getattr(schema, prop_name) is None:
                continue

            schema_path = SchemaPath(
                schema_kind=schema.kind,
                path_type=SchemaPathType.NODE,
                field_name=prop_name,
                property_name=prop_name,
            )
            constraint_name = f"node.{prop_name}.update"

            constraints.append(SchemaUpdateConstraintInfo(constraint_name=constraint_name, path=schema_path))
        return constraints

    async def _get_attribute_constraints_for_one_schema(
        self, schema: Union[NodeSchema, GenericSchema]
    ) -> list[SchemaUpdateConstraintInfo]:
        constraints: list[SchemaUpdateConstraintInfo] = []
        for field_name in schema.attribute_names:
            node_diffs_for_attribute = self._get_attribute_diffs(kind=schema.kind, name=field_name)
            if not node_diffs_for_attribute:
                continue
            field = schema.get_attribute(field_name)
            constraints.extend(await self._get_constraints_for_one_field(schema=schema, field=field))
        return constraints

    async def _get_relationship_constraints_for_one_schema(
        self, schema: Union[NodeSchema, GenericSchema]
    ) -> list[SchemaUpdateConstraintInfo]:
        constraints: list[SchemaUpdateConstraintInfo] = []
        for field_name in schema.relationship_names:
            node_diffs_for_relationship = self._get_relationship_diffs(kind=schema.kind, name=field_name)
            if not node_diffs_for_relationship:
                continue
            field = schema.get_relationship(field_name)
            constraints.extend(await self._get_constraints_for_one_field(schema=schema, field=field))
        return constraints

    async def _get_constraints_for_one_field(
        self, schema: Union[NodeSchema, GenericSchema], field: Union[AttributeSchema, RelationshipSchema]
    ) -> list[SchemaUpdateConstraintInfo]:
        constraints: list[SchemaUpdateConstraintInfo] = []
        for prop_name, prop_field_info in field.model_fields.items():
            if not prop_field_info.json_schema_extra or not isinstance(prop_field_info.json_schema_extra, dict):
                continue

            prop_field_update = prop_field_info.json_schema_extra.get("update")
            if prop_field_update != UpdateSupport.VALIDATE_CONSTRAINT.value:
                continue

            if getattr(field, prop_name) is None:
                continue

            path_type = SchemaPathType.ATTRIBUTE
            constraint_name = f"attribute.{prop_name}.update"
            if isinstance(field, RelationshipSchema):
                if field.kind == RelationshipKind.GROUP:
                    continue
                path_type = SchemaPathType.RELATIONSHIP
                constraint_name = f"relationship.{prop_name}.update"

            schema_path = SchemaPath(
                schema_kind=schema.kind,
                path_type=path_type,
                field_name=field.name,
                property_name=prop_name,
            )

            constraints.append(SchemaUpdateConstraintInfo(constraint_name=constraint_name, path=schema_path))
        return constraints
