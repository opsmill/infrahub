from dataclasses import dataclass, field

from infrahub import config
from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.diff.query_parser import DiffQueryParser
from infrahub.core.query.diff import (
    DiffCalculationQuery,
    DiffFieldPathsQuery,
    DiffNodePathsQuery,
    DiffPropertyPathsQuery,
)
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.log import get_logger

from .model.path import CalculatedDiffs

log = get_logger()


@dataclass
class DiffCalculationRequest:
    base_branch: Branch
    diff_branch: Branch
    branch_from_time: Timestamp
    from_time: Timestamp
    to_time: Timestamp
    current_node_field_specifiers: dict[str, set[str]] | None = field(default=None)
    new_node_field_specifiers: dict[str, set[str]] | None = field(default=None)


class DiffCalculator:
    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

    async def _run_diff_calculation_query(
        self,
        diff_parser: DiffQueryParser,
        query_class: type[DiffCalculationQuery],
        calculation_request: DiffCalculationRequest,
        limit: int,
    ) -> None:
        has_more_data = True
        offset = 0
        while has_more_data:
            diff_query = await query_class.init(
                db=self.db,
                branch=calculation_request.diff_branch,
                base_branch=calculation_request.base_branch,
                diff_branch_from_time=calculation_request.branch_from_time,
                diff_from=calculation_request.from_time,
                diff_to=calculation_request.to_time,
                current_node_field_specifiers=calculation_request.current_node_field_specifiers,
                new_node_field_specifiers=calculation_request.new_node_field_specifiers,
                limit=limit,
                offset=offset,
            )
            log.info(f"Beginning one diff calculation query {limit=}, {offset=}")
            await diff_query.execute(db=self.db)
            log.info("Diff calculation query complete")
            last_result = None
            for query_result in diff_query.get_results():
                diff_parser.read_result(query_result=query_result)
                last_result = query_result
            has_more_data = False
            if last_result:
                has_more_data = last_result.get_as_type("has_more_data", bool)
            offset += limit

    async def calculate_diff(
        self,
        base_branch: Branch,
        diff_branch: Branch,
        from_time: Timestamp,
        to_time: Timestamp,
        include_unchanged: bool = True,
        previous_node_specifiers: dict[str, set[str]] | None = None,
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
        node_limit = int(config.SETTINGS.database.query_size_limit / 10)
        fields_limit = int(config.SETTINGS.database.query_size_limit / 3)
        properties_limit = int(config.SETTINGS.database.query_size_limit)

        calculation_request = DiffCalculationRequest(
            base_branch=base_branch,
            diff_branch=diff_branch,
            branch_from_time=diff_branch_from_time,
            from_time=from_time,
            to_time=to_time,
        )

        log.info("Beginning diff node-level calculation queries for branch")
        await self._run_diff_calculation_query(
            diff_parser=diff_parser,
            query_class=DiffNodePathsQuery,
            calculation_request=calculation_request,
            limit=node_limit,
        )
        log.info("Diff node-level calculation queries for branch complete")

        log.info("Beginning diff field-level calculation queries for branch")
        await self._run_diff_calculation_query(
            diff_parser=diff_parser,
            query_class=DiffFieldPathsQuery,
            calculation_request=calculation_request,
            limit=fields_limit,
        )
        log.info("Diff field-level calculation queries for branch complete")

        log.info("Beginning diff property-level calculation queries for branch")
        await self._run_diff_calculation_query(
            diff_parser=diff_parser,
            query_class=DiffPropertyPathsQuery,
            calculation_request=calculation_request,
            limit=properties_limit,
        )
        log.info("Diff property-level calculation queries for branch complete")

        if base_branch.name != diff_branch.name:
            current_node_field_specifiers = diff_parser.get_current_node_field_specifiers()
            new_node_field_specifiers = diff_parser.get_new_node_field_specifiers()
            calculation_request = DiffCalculationRequest(
                base_branch=base_branch,
                diff_branch=base_branch,
                branch_from_time=diff_branch_from_time,
                from_time=from_time,
                to_time=to_time,
                current_node_field_specifiers=current_node_field_specifiers,
                new_node_field_specifiers=new_node_field_specifiers,
            )

            log.info("Beginning diff node-level calculation queries for base")
            await self._run_diff_calculation_query(
                diff_parser=diff_parser,
                query_class=DiffNodePathsQuery,
                calculation_request=calculation_request,
                limit=node_limit,
            )
            log.info("Diff node-level calculation queries for base complete")

            log.info("Beginning diff field-level calculation queries for base")
            await self._run_diff_calculation_query(
                diff_parser=diff_parser,
                query_class=DiffFieldPathsQuery,
                calculation_request=calculation_request,
                limit=fields_limit,
            )
            log.info("Diff field-level calculation queries for base complete")

            log.info("Beginning diff property-level calculation queries for base")
            await self._run_diff_calculation_query(
                diff_parser=diff_parser,
                query_class=DiffPropertyPathsQuery,
                calculation_request=calculation_request,
                limit=properties_limit,
            )
            log.info("Diff property-level calculation queries for base complete")

        log.info("Parsing calculated diff")
        diff_parser.parse(include_unchanged=include_unchanged)
        log.info("Calculated diff parsed")
        return CalculatedDiffs(
            base_branch_name=base_branch.name,
            diff_branch_name=diff_branch.name,
            base_branch_diff=diff_parser.get_diff_root_for_branch(branch=base_branch.name),
            diff_branch_diff=diff_parser.get_diff_root_for_branch(branch=diff_branch.name),
        )
