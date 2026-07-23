from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants import RelationshipKind, SchemaPathType
from infrahub.core.constants.schema import UpdateSupport
from infrahub.core.models import SchemaUpdateConstraintInfo
from infrahub.core.path import SchemaPath
from infrahub.core.schema.attribute_parameters import AttributeParameters
from infrahub.core.schema.relationship_schema import RelationshipSchema
from infrahub.core.validators import CONSTRAINT_VALIDATOR_MAP
from infrahub.core.validators.node_diff_index import NodeDiffIndex
from infrahub.core.validators.uniqueness.dependent_resolver import UniquenessDependentResolver
from infrahub.core.validators.uniqueness.scope import UniquenessConstraintScoper
from infrahub.exceptions import SchemaNotFoundError
from infrahub.log import get_logger

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo

    from infrahub.core.branch import Branch
    from infrahub.core.diff.model.path import NodeDiffFieldSummary
    from infrahub.core.schema import AttributeSchema, MainSchemaTypes
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase

LOG = get_logger(__name__)


class ConstraintValidatorDeterminer:
    def __init__(
        self,
        schema_branch: SchemaBranch,
        node_diff_index: NodeDiffIndex,
        uniqueness_scoper: UniquenessConstraintScoper,
    ) -> None:
        self.schema_branch = schema_branch
        self.node_diff_index = node_diff_index
        self.uniqueness_scoper = uniqueness_scoper

    async def get_constraints(
        self, node_diffs: list[NodeDiffFieldSummary], filter_invalid: bool = True
    ) -> list[SchemaUpdateConstraintInfo]:
        self.node_diff_index.initialize(node_diffs)
        constraints: list[SchemaUpdateConstraintInfo] = []
        if not node_diffs:
            return constraints

        constraints.extend(await self._get_property_constraints_for_impacted_kinds())

        for kind in self.node_diff_index.kinds:
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
        for kind in self.node_diff_index.kinds:
            schema = self._get_schema_or_none(kind=kind)
            if schema is None:
                continue
            kinds.add(kind)
            kinds.update(getattr(schema, "inherit_from", None) or [])
        return kinds

    def _node_property_triggered_by_diff(self, schema: MainSchemaTypes, prop_name: str) -> bool:
        """Return True if the diff touches a field guarded by the node-level property `prop_name`.

        A node-level constraint may be defined on a kind without every data change to that kind
        being able to violate it; emit only when a participating field is in the diff. Unknown
        properties default to emitting so a newly-added node-level constraint is never missed.
        """
        if prop_name == "uniqueness_constraints":
            return self.uniqueness_scoper.requires_validation(schema=schema)
        if prop_name in ("parent", "children"):
            return self.node_diff_index.has_relationship_diff(kind=schema.kind, name=prop_name)
        return True

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
            if self.uniqueness_scoper.requires_validation(schema=schema):
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

            if not self._node_property_triggered_by_diff(schema=schema, prop_name=prop_name):
                # the node-level constraint is defined on this kind, but no field it guards is in
                # the diff, so a data change cannot violate it
                continue

            node_uuids: list[str] | None = None
            if prop_name == "uniqueness_constraints":
                node_uuids = await self.uniqueness_scoper.affected_node_uuids(schema=schema)

            constraints.append(
                SchemaUpdateConstraintInfo(constraint_name=constraint_name, path=schema_path, node_uuids=node_uuids)
            )
        return constraints

    async def _get_attribute_constraints_for_one_schema(
        self, schema: MainSchemaTypes
    ) -> list[SchemaUpdateConstraintInfo]:
        constraints: list[SchemaUpdateConstraintInfo] = []
        for field_name in schema.attribute_names:
            if self.node_diff_index.has_attribute_diff(kind=schema.kind, name=field_name):
                field = schema.get_attribute(field_name)
                constraints.extend(await self._get_constraints_for_one_field(schema=schema, field=field))
        return constraints

    async def _get_relationship_constraints_for_one_schema(
        self, schema: MainSchemaTypes
    ) -> list[SchemaUpdateConstraintInfo]:
        constraints: list[SchemaUpdateConstraintInfo] = []
        for field_name in schema.relationship_names:
            if self.node_diff_index.has_relationship_diff(kind=schema.kind, name=field_name):
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


def build_constraint_validator_determiner(
    db: InfrahubDatabase,
    branch: Branch,
    schema_branch: SchemaBranch,
    at: Timestamp | str | None = None,
) -> ConstraintValidatorDeterminer:
    """Wire a determiner with its node-diff index and uniqueness scoper for a single operation."""
    node_diff_index = NodeDiffIndex()
    uniqueness_scoper = UniquenessConstraintScoper(
        schema_branch=schema_branch,
        dependent_resolver=UniquenessDependentResolver(db=db, branch=branch, at=at),
        node_diff_index=node_diff_index,
    )
    return ConstraintValidatorDeterminer(
        schema_branch=schema_branch, node_diff_index=node_diff_index, uniqueness_scoper=uniqueness_scoper
    )
