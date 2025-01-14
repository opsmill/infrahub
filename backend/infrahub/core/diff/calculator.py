from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.diff.query_parser import DiffQueryParser
from infrahub.core.query.diff import DiffAllPathsQuery
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.log import get_logger

from .model.path import CalculatedDiffs, NodeFieldSpecifier

log = get_logger()


class DiffCalculator:
    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

    async def calculate_diff(
        self,
        base_branch: Branch,
        diff_branch: Branch,
        from_time: Timestamp,
        to_time: Timestamp,
        include_unchanged: bool = True,
        previous_node_specifiers: set[NodeFieldSpecifier] | None = None,
    ) -> CalculatedDiffs:
        if diff_branch.name == registry.default_branch:
            diff_branch_from_time = from_time
        else:
            diff_branch_from_time = Timestamp(diff_branch.get_branched_from())
        diff_parser = DiffQueryParser(
            base_branch=base_branch,
            diff_branch=diff_branch,
            schema_manager=registry.schema,
            from_time=from_time,
            to_time=to_time,
            previous_node_field_specifiers=previous_node_specifiers,
        )
        branch_diff_query = await DiffAllPathsQuery.init(
            db=self.db,
            branch=diff_branch,
            base_branch=base_branch,
            diff_branch_from_time=diff_branch_from_time,
            diff_from=from_time,
            diff_to=to_time,
        )
        log.info("Beginning diff calculation query for branch")
        await branch_diff_query.execute(db=self.db)
        log.info("Diff calculation query for branch complete")
        log.info("Reading results of query for branch")
        for query_result in branch_diff_query.get_results():
            diff_parser.read_result(query_result=query_result)
        log.info("Results of query for branch read")

        if base_branch.name != diff_branch.name:
            new_node_field_specifiers = diff_parser.get_new_node_field_specifiers()
            current_node_field_specifiers = diff_parser.get_current_node_field_specifiers()

            base_diff_query = await DiffAllPathsQuery.init(
                db=self.db,
                branch=base_branch,
                base_branch=base_branch,
                diff_branch_from_time=diff_branch_from_time,
                diff_from=from_time,
                diff_to=to_time,
                current_node_field_specifiers=[
                    (nfs.node_uuid, nfs.field_name) for nfs in current_node_field_specifiers
                ],
                new_node_field_specifiers=[(nfs.node_uuid, nfs.field_name) for nfs in new_node_field_specifiers],
            )

            log.info("Beginning diff calculation query for base")
            await base_diff_query.execute(db=self.db)
            log.info("Diff calculation query for base complete")
            log.info("Reading results of query for base")
            for query_result in base_diff_query.get_results():
                diff_parser.read_result(query_result=query_result)
            log.info("Results of query for branch read")
        log.info("Parsing calculated diff")
        diff_parser.parse(include_unchanged=include_unchanged)
        log.info("Calculated diff parsed")
        return CalculatedDiffs(
            base_branch_name=base_branch.name,
            diff_branch_name=diff_branch.name,
            base_branch_diff=diff_parser.get_diff_root_for_branch(branch=base_branch.name),
            diff_branch_diff=diff_parser.get_diff_root_for_branch(branch=diff_branch.name),
        )
