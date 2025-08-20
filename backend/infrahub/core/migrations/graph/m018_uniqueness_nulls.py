from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Sequence

from infrahub.core import registry
from infrahub.core.diff.payload_builder import get_display_labels_per_kind
from infrahub.core.migrations.shared import MigrationResult
from infrahub.core.schema import GenericSchema, NodeSchema, SchemaRoot, internal_schema
from infrahub.core.schema.manager import SchemaManager
from infrahub.core.validators.uniqueness.checker import UniquenessChecker
from infrahub.dependencies.registry import build_component_registry, get_component_registry
from infrahub.log import get_logger

from ..shared import InternalSchemaMigration, SchemaMigration

if TYPE_CHECKING:
    from infrahub.core.validators.uniqueness.model import NonUniqueNode
    from infrahub.database import InfrahubDatabase

log = get_logger()


async def validate_nulls_in_uniqueness_constraints(db: InfrahubDatabase) -> MigrationResult:
    """
    Validate any schema that include optional attributes in the uniqueness constraints

    An update to uniqueness constraint validation now handles NULL values as unique instead of ignoring them
    """

    default_branch = registry.get_branch_from_registry()
    build_component_registry()
    component_registry = get_component_registry()
    uniqueness_checker = await component_registry.get_component(UniquenessChecker, db=db, branch=default_branch)
    non_unique_nodes_by_kind: dict[str, list[NonUniqueNode]] = defaultdict(list)

    manager = SchemaManager()
    registry.schema = manager
    internal_schema_root = SchemaRoot(**internal_schema)
    manager.register_schema(schema=internal_schema_root)
    schema_branch = await manager.load_schema_from_db(db=db, branch=default_branch)
    manager.set_schema_branch(name=default_branch.name, schema=schema_branch)

    for schema_kind in schema_branch.node_names + schema_branch.generic_names_without_templates:
        schema = schema_branch.get(name=schema_kind, duplicate=False)
        if not isinstance(schema, NodeSchema | GenericSchema):
            continue

        uniqueness_constraint_paths = schema.get_unique_constraint_schema_attribute_paths(schema_branch=schema_branch)
        includes_optional_attr: bool = False

        for uniqueness_constraint_path in uniqueness_constraint_paths:
            for schema_attribute_path in uniqueness_constraint_path.attributes_paths:
                if schema_attribute_path.attribute_schema and schema_attribute_path.attribute_schema.optional is True:
                    includes_optional_attr = True
                    break

        if not includes_optional_attr:
            continue

        non_unique_nodes = await uniqueness_checker.check_one_schema(schema=schema)
        if non_unique_nodes:
            non_unique_nodes_by_kind[schema_kind] = non_unique_nodes

    if not non_unique_nodes_by_kind:
        return MigrationResult()

    error_strings = []
    for schema_kind, non_unique_nodes in non_unique_nodes_by_kind.items():
        display_label_map = await get_display_labels_per_kind(
            db=db, kind=schema_kind, branch_name=default_branch.name, ids=[nun.node_id for nun in non_unique_nodes]
        )
        for non_unique_node in non_unique_nodes:
            display_label = display_label_map.get(non_unique_node.node_id)
            error_str = f"{display_label or ''}({non_unique_node.node_schema.kind} / {non_unique_node.node_id})"
            error_str += " violates uniqueness constraints for the following attributes: "
            attr_values = [
                f"{attr.attribute_name}={attr.attribute_value}" for attr in non_unique_node.non_unique_attributes
            ]
            error_str += ", ".join(attr_values)
            error_strings.append(error_str)
    if error_strings:
        error_str = "For the following nodes, you must update the uniqueness_constraints on the schema of the node"
        error_str += " to remove the attribute(s) with NULL values or update the data on the nodes to be unique"
        error_str += " now that NULL values are considered during uniqueness validation"
        return MigrationResult(errors=[error_str] + error_strings)
    return MigrationResult()


class Migration018(InternalSchemaMigration):
    name: str = "018_validate_nulls_in_uniqueness_constraints"
    minimum_version: int = 17
    migrations: Sequence[SchemaMigration] = []

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()

    async def execute(self, db: InfrahubDatabase) -> MigrationResult:
        return await validate_nulls_in_uniqueness_constraints(db=db)
