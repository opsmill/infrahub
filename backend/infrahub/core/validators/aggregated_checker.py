from __future__ import annotations

from itertools import chain
from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.exceptions import ValidationError

from .model import SchemaViolation

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.path import DataPath, GroupedDataPaths
    from infrahub.database import InfrahubDatabase

    from .interface import ConstraintCheckerInterface
    from .model import SchemaConstraintValidatorRequest


class AggregatedConstraintChecker:
    def __init__(
        self, constraints: list[ConstraintCheckerInterface], db: InfrahubDatabase, branch: Branch | None = None
    ):
        self.constraints = constraints
        self.db = db
        self.branch = branch

    async def run_constraints(self, request: SchemaConstraintValidatorRequest) -> list[SchemaViolation]:
        grouped_data_paths_by_constraint_name: dict[str, list[GroupedDataPaths]] = {}
        for constraint in self.constraints:
            if constraint.supports(request):
                grouped_data_paths_by_constraint_name[constraint.name] = await constraint.check(request)

        ids: list[str] = []
        for grouped_path in chain(*grouped_data_paths_by_constraint_name.values()):
            ids.extend([path.node_id for path in grouped_path.get_all_data_paths()])
        # Try to query the nodes with their display label
        # it's possible that it might not work if the obj is not valid with the schema
        fields = {"display_label": None, request.schema_path.field_name: None}
        try:
            nodes = await registry.manager.get_many(db=self.db, ids=ids, branch=self.branch, fields=fields)
        except ValidationError:
            nodes = {}

        violations = []
        for constraint_name, grouped_paths in grouped_data_paths_by_constraint_name.items():
            for path in chain(*[gp.get_all_data_paths() for gp in grouped_paths]):
                node = nodes.get(path.node_id)
                node_display_label = None
                display_label = None
                if node:
                    node_display_label = await node.render_display_label(db=self.db)
                if node_display_label:
                    if request.node_schema.display_labels and node:
                        display_label = f"Node {node_display_label} ({node.get_kind()}: {path.node_id})"
                    else:
                        display_label = f"Node {node_display_label}"
                if not display_label:
                    display_label = f"Node ({path.kind}: {path.node_id})"

                violation = SchemaViolation(
                    node_id=path.node_id,
                    node_kind=path.kind,
                    display_label=node_display_label or display_label,
                    full_display_label=display_label,
                )
                violation.message = await self.render_error_request(
                    violation=violation, constraint_name=constraint_name, data_path=path
                )
                violations.append(violation)
        return violations

    async def render_error_request(
        self,
        violation: SchemaViolation,
        constraint_name: str,
        data_path: DataPath,
    ) -> str:
        constraint_name_str = constraint_name
        if constraint_name.count(".") == 2:
            constraint_level, constraint_name_str, _ = constraint_name.split(".", maxsplit=2)
            error_str = f"{constraint_level.title()}-level '{constraint_name_str}'"
        else:
            error_str = f"'{constraint_name_str}'"
        error_str += f" constraint violation on schema '{violation.node_kind}'."
        if violation.display_label.startswith("Node"):
            error_str += f" {violation.display_label}"
        else:
            error_str += f" Node ({violation.display_label})"
        error_str += " is not compliant."
        error_detail_str_list = []
        if data_path.field_name:
            if data_path.value:
                error_detail_str = data_path.field_name
                if data_path.property_name:
                    error_detail_str += f".{data_path.property_name}"
                error_detail_str += f"={data_path.value!r}"
                error_detail_str_list.append(error_detail_str)
            if data_path.peer_id:
                error_detail_str += f"{data_path.field_name}.id={data_path.peer_id}"
                error_detail_str_list.append(error_detail_str)
            if error_detail_str:
                error_str += " The error relates to field "
                error_str += ",".join(error_detail_str_list)
                error_str += "."
        return error_str
