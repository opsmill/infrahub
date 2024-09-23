from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.diff.query_parser import DiffQueryParser
from infrahub.core.query.diff import DiffAllPathsQuery
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase

from .model.path import CalculatedDiffs, NodeFieldSpecifier


class DiffCalculator:
    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

    async def calculate_diff(
        self,
        base_branch: Branch,
        diff_branch: Branch,
        from_time: Timestamp,
        to_time: Timestamp,
        extra_node_specifiers: set[NodeFieldSpecifier] | None,
    ) -> CalculatedDiffs:
        diff_query = await DiffAllPathsQuery.init(
            db=self.db,
            branch=diff_branch,
            base_branch=base_branch,
            diff_from=from_time,
            diff_to=to_time,
            node_field_specifiers=[(ens.node_uuid, ens.field_name) for ens in extra_node_specifiers]
            if extra_node_specifiers
            else None,
        )
        await diff_query.execute(db=self.db)
        diff_parser = DiffQueryParser(
            diff_query=diff_query,
            base_branch=base_branch,
            diff_branch=diff_branch,
            schema_manager=registry.schema,
            from_time=from_time,
            to_time=to_time,
        )
        diff_parser.parse()
        return CalculatedDiffs(
            base_branch_name=base_branch.name,
            diff_branch_name=diff_branch.name,
            base_branch_diff=diff_parser.get_diff_root_for_branch(branch=base_branch.name),
            diff_branch_diff=diff_parser.get_diff_root_for_branch(branch=diff_branch.name),
        )
