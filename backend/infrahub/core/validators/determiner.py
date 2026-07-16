from typing import TYPE_CHECKING, Any

from infrahub.core.constants import RelationshipKind, SchemaPathType
from infrahub.core.constants.schema import UpdateSupport
from infrahub.core.diff.model.path import NodeDiffFieldSummary
from infrahub.core.models import SchemaUpdateConstraintInfo
from infrahub.core.path import SchemaPath
from infrahub.core.schema import AttributePathParsingError, AttributeSchema, MainSchemaTypes
from infrahub.core.schema.attribute_parameters import AttributeParameters
from infrahub.core.schema.relationship_schema import RelationshipSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.validators import CONSTRAINT_VALIDATOR_MAP
from infrahub.exceptions import SchemaNotFoundError
from infrahub.log import get_logger

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo

LOG = get_logger(__name__)


class ConstraintValidatorDeterminer:
    def __init__(self, schema_branch: SchemaBranch) -> None:
        self.schema_branch = schema_branch
        self._node_kinds: set[str] = set()
        self._attribute_element_map: dict[str, set[str]] = {}
        self._relationship_element_map: dict[str, set[str]] = {}

    def _index_node_diffs(self, node_diffs: list[NodeDiffFieldSummary]) -> None:
        for node_diff in node_diffs:
            self._node_kinds.add(node_diff.kind)
            if node_diff.kind not in self._attribute_element_map:
                self._attribute_element_map[node_diff.kind] = set()
            for attribute_name in node_diff.attribute_names:
                self._attribute_element_map[node_diff.kind].add(attribute_name)
            if node_diff.kind not in self._relationship_element_map:
                self._relationship_element_map[node_diff.kind] = set()
            for relationship_name in node_diff.relationship_names:
                self._relationship_element_map[node_diff.kind].add(relationship_name)

    def _has_attribute_diff(self, kind: str, name: str) -> bool:
        return name in self._attribute_element_map.get(kind, set())

    def _has_relationship_diff(self, kind: str, name: str) -> bool:
        return name in self._relationship_element_map.get(kind, set())

    async def get_constraints(
        self, node_diffs: list[NodeDiffFieldSummary], filter_invalid: bool = True
    ) -> list[SchemaUpdateConstraintInfo]:
        self._index_node_diffs(node_diffs)
        constraints: list[SchemaUpdateConstraintInfo] = []
        if not node_diffs:
            return constraints

        constraints.extend(await self._get_property_constraints_for_impacted_kinds())

        for kind in self._node_kinds:
            schema = self._get_schema_or_none(kind=kind)
            if schema is None:
                # a branch can hold data changes for a kind whose schema it also deletes
                LOG.info("Skipping constraints for kind absent from the schema", kind=kind)
                continue
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

    async def _get_constraints_for_one_schema(self, schema: MainSchemaTypes) -> list[SchemaUpdateConstraintInfo]:
        constraints: list[SchemaUpdateConstraintInfo] = []
        constraints.extend(await self._get_attribute_constraints_for_one_schema(schema=schema))
        constraints.extend(await self._get_relationship_constraints_for_one_schema(schema=schema))
        return constraints

    def _get_schema_or_none(self, kind: str) -> MainSchemaTypes | None:
        try:
            return self.schema_branch.get(name=kind, duplicate=False)
        except SchemaNotFoundError:
            return None

    def _get_impacted_kinds(self) -> set[str]:
        """Kinds with node-level property constraints that could be violated by the data diff.

        Includes the kinds present in the diff and the generics they inherit from, since a
        generic-level uniqueness check spans every implementing node.
        """
        kinds: set[str] = set()
        for kind in self._node_kinds:
            schema = self._get_schema_or_none(kind=kind)
            if schema is None:
                continue
            kinds.add(kind)
            kinds.update(getattr(schema, "inherit_from", None) or [])
        return kinds

    def _has_uniqueness_constraint_on_peer(self, schema: MainSchemaTypes, peer_kinds: set[str]) -> bool:
        """Return True if a uniqueness constraint of `schema` reads an attribute of a peer in `peer_kinds`.

        A constraint element such as "owner__name" compares the value of an attribute on the
        related node, so a data change on the peer kind can create a violation without any
        change to the constrained kind itself.
        """
        for constraint_paths in schema.uniqueness_constraints or []:
            for constraint_path in constraint_paths:
                try:
                    schema_path = schema.parse_schema_path(path=constraint_path, schema=self.schema_branch)
                except AttributePathParsingError:
                    continue
                if (
                    schema_path.is_type_relationship
                    and schema_path.attribute_schema is not None
                    and schema_path.active_relationship_schema.peer in peer_kinds
                ):
                    return True
        return False

    async def _get_property_constraints_for_impacted_kinds(self) -> list[SchemaUpdateConstraintInfo]:
        impacted_kinds = self._get_impacted_kinds()
        schemas: list[MainSchemaTypes] = []
        for kind in impacted_kinds:
            schema = self._get_schema_or_none(kind=kind)
            if schema is not None:
                schemas.append(schema)
        for schema in self.schema_branch.get_all(duplicate=False).values():
            if schema.kind in impacted_kinds:
                continue
            if self._has_uniqueness_constraint_on_peer(schema=schema, peer_kinds=impacted_kinds):
                schemas.append(schema)

        constraints: list[SchemaUpdateConstraintInfo] = []
        for schema in schemas:
            constraints.extend(await self._get_property_constraints_for_one_schema(schema=schema))
        return constraints

    async def _get_property_constraints_for_one_schema(
        self, schema: MainSchemaTypes
    ) -> list[SchemaUpdateConstraintInfo]:
        constraints: list[SchemaUpdateConstraintInfo] = []
        for prop_name, prop_field_info in schema.__class__.model_fields.items():
            if (
                prop_name in ["attributes", "relationships"]
                or not prop_field_info.json_schema_extra
                or not isinstance(prop_field_info.json_schema_extra, dict)
            ):
                continue

            prop_field_update = prop_field_info.json_schema_extra.get("update")
            if prop_field_update not in (
                UpdateSupport.VALIDATE_CONSTRAINT.value,
                UpdateSupport.MIGRATION_REQUIRED.value,
            ):
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

            checker = CONSTRAINT_VALIDATOR_MAP.get(constraint_name)
            if checker is not None and not checker.triggered_by_data_change:
                # a data change cannot violate a constraint whose checker only compares the
                # candidate schema against the current one; that case belongs to the schema diff
                continue

            do_constraint_validation = prop_field_update == UpdateSupport.VALIDATE_CONSTRAINT.value or (
                prop_field_update == UpdateSupport.MIGRATION_REQUIRED.value and checker
            )
            if not do_constraint_validation:
                continue

            constraints.append(SchemaUpdateConstraintInfo(constraint_name=constraint_name, path=schema_path))
        return constraints

    async def _get_attribute_constraints_for_one_schema(
        self, schema: MainSchemaTypes
    ) -> list[SchemaUpdateConstraintInfo]:
        constraints: list[SchemaUpdateConstraintInfo] = []
        for field_name in schema.attribute_names:
            if self._has_attribute_diff(kind=schema.kind, name=field_name):
                field = schema.get_attribute(field_name)
                constraints.extend(await self._get_constraints_for_one_field(schema=schema, field=field))
        return constraints

    async def _get_relationship_constraints_for_one_schema(
        self, schema: MainSchemaTypes
    ) -> list[SchemaUpdateConstraintInfo]:
        constraints: list[SchemaUpdateConstraintInfo] = []
        for field_name in schema.relationship_names:
            if self._has_relationship_diff(kind=schema.kind, name=field_name):
                field = schema.get_relationship(field_name)
                constraints.extend(await self._get_constraints_for_one_field(schema=schema, field=field))
        return constraints

    async def _get_constraints_for_one_field(
        self, schema: MainSchemaTypes, field: AttributeSchema | RelationshipSchema
    ) -> list[SchemaUpdateConstraintInfo]:
        constraints: list[SchemaUpdateConstraintInfo] = []
        prop_details_list: list[tuple[str, FieldInfo, Any]] = []
        for p_name, p_info in field.__class__.model_fields.items():
            p_value = getattr(field, p_name)
            if isinstance(p_value, AttributeParameters):
                for parameter_name, parameter_field_info in p_value.__class__.model_fields.items():
                    parameter_value = getattr(p_value, parameter_name)
                    prop_details_list.append((f"{p_name}.{parameter_name}", parameter_field_info, parameter_value))
            else:
                prop_details_list.append((p_name, p_info, p_value))

        for prop_name, prop_field_info, prop_value in prop_details_list:
            if not prop_field_info.json_schema_extra or not isinstance(prop_field_info.json_schema_extra, dict):
                continue

            prop_field_update = prop_field_info.json_schema_extra.get("update")
            if prop_field_update not in (
                UpdateSupport.VALIDATE_CONSTRAINT.value,
                UpdateSupport.MIGRATION_REQUIRED.value,
            ):
                continue

            if prop_value is None:
                continue

            path_type = SchemaPathType.ATTRIBUTE
            constraint_name = f"attribute.{prop_name}.update"
            if isinstance(field, RelationshipSchema):
                if field.kind == RelationshipKind.GROUP:
                    continue
                path_type = SchemaPathType.RELATIONSHIP
                constraint_name = f"relationship.{prop_name}.update"

            checker = CONSTRAINT_VALIDATOR_MAP.get(constraint_name)
            if checker is not None and not checker.triggered_by_data_change:
                # a data change cannot violate a constraint whose checker only compares the
                # candidate schema against the current one; that case belongs to the schema diff
                continue

            do_constraint_validation = prop_field_update == UpdateSupport.VALIDATE_CONSTRAINT.value or (
                prop_field_update == UpdateSupport.MIGRATION_REQUIRED.value and checker
            )
            if not do_constraint_validation:
                continue

            schema_path = SchemaPath(
                schema_kind=schema.kind,
                path_type=path_type,
                field_name=field.name,
                property_name=prop_name,
            )

            constraints.append(SchemaUpdateConstraintInfo(constraint_name=constraint_name, path=schema_path))
        return constraints
