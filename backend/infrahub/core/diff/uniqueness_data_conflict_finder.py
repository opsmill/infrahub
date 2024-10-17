from infrahub.core.branch import Branch
from infrahub.core.constants import DiffAction, SchemaPathType
from infrahub.core.path import SchemaPath
from infrahub.core.schema.profile_schema import ProfileSchema
from infrahub.core.validators.model import SchemaConstraintValidatorRequest
from infrahub.core.validators.uniqueness.checker import UniquenessChecker
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import SchemaNotFoundError

from .model.diff import BranchChanges, DataConflict, ModifiedPathType
from .model.path import EnrichedDiffRoot


class DiffUniquenessDataConflictFinder:
    def __init__(self, db: InfrahubDatabase, uniqueness_checker: UniquenessChecker):
        self.db = db
        self.uniqueness_checker = uniqueness_checker

    async def get_data_conflicts(
        self, enriched_diff: EnrichedDiffRoot, source_branch: Branch, destination_branch: Branch
    ) -> list[DataConflict]:
        updated_schema_kinds = set()
        for node in enriched_diff.nodes:
            if node.action in (DiffAction.UPDATED, DiffAction.ADDED):
                updated_schema_kinds.add(node.kind)
        uniqueness_data_conflicts: list[DataConflict] = []
        for schema_kind in updated_schema_kinds:
            try:
                node_schema = self.db.schema.get(name=schema_kind, branch=source_branch, duplicate=False)
            except SchemaNotFoundError:
                node_schema = self.db.schema.get(name=schema_kind, branch=destination_branch, duplicate=False)
            if isinstance(node_schema, ProfileSchema):
                continue
            grouped_data_paths = await self.uniqueness_checker.check(
                request=SchemaConstraintValidatorRequest(
                    branch=source_branch,
                    constraint_name="node.uniqueness_constraints.check",
                    node_schema=node_schema,
                    schema_path=SchemaPath(path_type=SchemaPathType.NODE, schema_kind=schema_kind),
                )
            )
            if not grouped_data_paths:
                continue
            for gdp in grouped_data_paths:
                for data_path in gdp.get_all_data_paths():
                    uniqueness_data_conflicts.append(
                        DataConflict(
                            name=data_path.field_name or "",
                            type=ModifiedPathType.DATA.value,
                            id=data_path.node_id,
                            kind=data_path.kind,
                            change_type=f"{data_path.path_type.value}_value",
                            path=data_path.get_path(),
                            conflict_path=data_path.get_path(),
                            path_type=data_path.path_type,
                            property_name=data_path.property_name,
                            changes=[
                                BranchChanges(
                                    branch=data_path.branch,
                                    action=DiffAction.UNCHANGED,
                                    previous=data_path.value,
                                    new=data_path.value,
                                ),
                            ],
                        )
                    )
        return uniqueness_data_conflicts
