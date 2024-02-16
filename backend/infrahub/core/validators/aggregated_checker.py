from __future__ import annotations

from itertools import chain
from typing import TYPE_CHECKING, Dict, List, Optional

from dependencies.registry import get_component_registry

from infrahub.core import registry
from infrahub.core.attribute_path.parser import AttributePathParser
from infrahub.core.display_label.renderer import DisplayLabelRenderer
from infrahub.core.validators.uniqueness.checker import UniquenessChecker
from infrahub.exceptions import ValidationError

from .attribute.regex import AttributeRegexChecker
from .attribute.unique import AttributeUniquenessChecker
from .model import SchemaViolation
from .relationship.optional import RelationshipOptionalChecker

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.path import GroupedDataPaths
    from infrahub.database import InfrahubDatabase

    from .interface import ConstraintCheckerInterface
    from .model import SchemaConstraintValidatorRequest


class AggregatedConstraintChecker:
    def __init__(
        self,
        constraints: List[ConstraintCheckerInterface],
        display_label_renderer: DisplayLabelRenderer,
        db: InfrahubDatabase,
        branch: Optional[Branch] = None,
    ):
        self.constraints = constraints
        self.display_label_renderer = display_label_renderer
        self.db = db
        self.branch = branch

    async def run_constraints(self, request: SchemaConstraintValidatorRequest) -> List[SchemaViolation]:
        grouped_data_paths_by_constraint_name: Dict[str, List[GroupedDataPaths]] = {}
        for constraint in self.constraints:
            if constraint.supports(request):
                grouped_data_paths_by_constraint_name[constraint.name] = await constraint.check(request)

        ids: List[str] = []
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
                if node:
                    node_display_label = await self.display_label_renderer.render(node, branch=self.branch)
                    if request.node_schema.display_labels:
                        display_label = f"Node {node_display_label} ({node.get_kind()}: {path.node_id})"
                    else:
                        display_label = f"Node {node_display_label}"
                else:
                    display_label = f"Node ({path.kind}: {path.node_id})"

                violation = SchemaViolation(
                    node_id=path.node_id,
                    node_kind=path.kind,
                    display_label=node_display_label or display_label,
                    full_display_label=display_label,
                )
                violation.message = await self.render_error_request(
                    violation=violation, constraint_name=constraint_name, request=request
                )
                violations.append(violation)
        return violations

    async def render_error_request(
        self, violation: SchemaViolation, constraint_name: str, request: SchemaConstraintValidatorRequest
    ) -> str:
        return f"{violation.full_display_label} is not compatible with the constraint {constraint_name!r} at {request.schema_path.get_path()!r}"


# TODO: move to dependencies
def build_aggregated_constraint_checker(db: InfrahubDatabase, branch: Optional[Branch]) -> AggregatedConstraintChecker:
    aggregated_constraint_checker = AggregatedConstraintChecker(
        constraints=[
            RelationshipOptionalChecker(db=db, branch=branch),
            AttributeRegexChecker(db=db, branch=branch),
            AttributeUniquenessChecker(db=db, branch=branch),
            UniquenessChecker(
                db=db, attribute_path_parser=get_component_registry().get_component(AttributePathParser), branch=branch
            ),
        ],
        display_label_renderer=get_component_registry().get_component(DisplayLabelRenderer),
        db=db,
        branch=branch,
    )
    return aggregated_constraint_checker
