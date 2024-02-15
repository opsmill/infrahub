from __future__ import annotations

from itertools import chain
from typing import TYPE_CHECKING, Dict, List, Optional

from infrahub.core import registry
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
    from infrahub.message_bus.messages.schema_validator_path import SchemaValidatorPath

    from .interface import ConstraintCheckerInterface


class AggregatedConstraintChecker:
    def __init__(
        self, constraints: List[ConstraintCheckerInterface], db: InfrahubDatabase, branch: Optional[Branch] = None
    ):
        self.constraints = constraints
        self.db = db
        self.branch = branch

    async def run_constraints(self, message: SchemaValidatorPath) -> List[SchemaViolation]:
        grouped_data_paths_by_constraint_name: Dict[str, List[GroupedDataPaths]] = {}
        for constraint in self.constraints:
            if constraint.supports(message):
                grouped_data_paths_by_constraint_name[constraint.name] = await constraint.check(message)

        ids: List[str] = []
        for grouped_path in chain(*grouped_data_paths_by_constraint_name.values()):
            ids.extend([path.node_id for path in grouped_path.get_all_data_paths()])
        # Try to query the nodes with their display label
        # it's possible that it might not work if the obj is not valid with the schema
        fields = {"display_label": None, message.schema_path.field_name: None}
        try:
            nodes = await registry.manager.get_many(db=self.db, ids=ids, branch=self.branch, fields=fields)
        except ValidationError:
            nodes = {}

        violations = []
        for constraint_name, grouped_paths in grouped_data_paths_by_constraint_name.items():
            for path in chain(*[gp.get_all_data_paths() for gp in grouped_paths]):
                node = nodes.get(path.node_id, None)
                node_display_label = None
                if node:
                    node_display_label = await node.render_display_label()
                    if message.node_schema.display_labels:
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
                violation.message = await self.render_error_message(
                    violation=violation, constraint_name=constraint_name, message=message
                )
                violations.append(violation)
        return violations

    async def render_error_message(
        self, violation: SchemaViolation, constraint_name: str, message: SchemaValidatorPath
    ) -> str:
        return f"{violation.full_display_label} is not compatible with the constraint {constraint_name!r} at {message.schema_path.get_path()!r}"


def build_aggregated_constraint_checker(db: InfrahubDatabase, branch: Optional[Branch]) -> AggregatedConstraintChecker:
    relationship_optional_checker = RelationshipOptionalChecker(db=db, branch=branch)
    attribute_regex_checker = AttributeRegexChecker(db=db, branch=branch)
    attribute_uniqueness_checker = AttributeUniquenessChecker(db=db, branch=branch)
    uniqueness_constraint_checker = UniquenessChecker(db=db, branch=branch)
    aggregated_constraint_checker = AggregatedConstraintChecker(
        [
            relationship_optional_checker,
            attribute_regex_checker,
            attribute_uniqueness_checker,
            uniqueness_constraint_checker,
        ],
        db,
        branch=branch,
    )
    return aggregated_constraint_checker
