"""The bulk merge queries start from the edges of the source branch, through their `branch` index."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core.diff.query.bulk_merge import (
    BulkMergeAttributePropertyEdgesQuery,
    BulkMergeNodeExistenceQuery,
    BulkMergeRelationshipEdgesQuery,
    BulkMergeRelationshipPropertyEdgesQuery,
)
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.core.timestamp import Timestamp
from tests.helpers.planner_statistics import refresh_planner_statistics
from tests.helpers.query_plan import explain_plan_operators

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.query import Query
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase

# With this many people and cars on main, the planner reads whole labels for a query that gives it no index hint.
MAIN_PERSON_COUNT = 300
WHOLE_GRAPH_SCANS = ("AllNodesScan", "AllRelationshipsScan", "RelationshipTypeScan", "RelationshipTypesScan")
GRAPH_LABELS = ("Node", "Attribute", "Relationship")


@dataclass(frozen=True)
class BulkMergeQueryCase:
    name: str
    query_class: type[Query]
    exclusions: dict[str, Any] = field(default_factory=dict)


CASES = [
    BulkMergeQueryCase(
        name="node-existence", query_class=BulkMergeNodeExistenceQuery, exclusions={"excluded_node_uuids": []}
    ),
    BulkMergeQueryCase(
        name="relationship-edges",
        query_class=BulkMergeRelationshipEdgesQuery,
        exclusions={"excluded_node_uuids": [], "excluded_relationship_paths": []},
    ),
    BulkMergeQueryCase(
        name="attribute-property-edges",
        query_class=BulkMergeAttributePropertyEdgesQuery,
        exclusions={"excluded_node_uuids": [], "excluded_attribute_property_paths": []},
    ),
    BulkMergeQueryCase(
        name="relationship-property-edges",
        query_class=BulkMergeRelationshipPropertyEdgesQuery,
        exclusions={
            "excluded_node_uuids": [],
            "excluded_relationship_paths": [],
            "excluded_relationship_property_paths": [],
        },
    ),
]


def _scans_the_graph(operator: str) -> bool:
    operator_type, _, details = operator.partition(": ")
    if any(scan in operator_type for scan in WHOLE_GRAPH_SCANS):
        return True
    return "NodeByLabelScan" in operator_type and details.rsplit(":", maxsplit=1)[-1] in GRAPH_LABELS


class TestBulkMergeQueryPlans:
    @pytest.fixture(scope="class")
    async def source_branch(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, car_person_schema_scope_class: SchemaBranch
    ) -> Branch:
        for index in range(MAIN_PERSON_COUNT):
            person = await Node.init(db=db, schema="TestPerson", branch=default_branch_scope_class)
            await person.new(db=db, name=f"person-{index}", height=index)
            await person.save(db=db)
            car = await Node.init(db=db, schema="TestCar", branch=default_branch_scope_class)
            await car.new(db=db, name=f"car-{index}", nbr_seats=4, is_electric=False, owner=person)
            await car.save(db=db)
        branch = await create_branch(db=db, branch_name="plan-source")
        person = await Node.init(db=db, schema="TestPerson", branch=branch)
        await person.new(db=db, name="person-on-branch", height=1)
        await person.save(db=db)
        await refresh_planner_statistics(db=db)
        return branch

    @pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
    async def test_bulk_merge_query_starts_from_the_source_branch(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, source_branch: Branch, case: BulkMergeQueryCase
    ) -> None:
        query = await case.query_class.init(
            db=db, branch=source_branch, at=Timestamp(), target_branch=default_branch_scope_class, **case.exclusions
        )

        plan_operators = await explain_plan_operators(db=db, query=query)

        # A read that starts from every vertex of a label or every edge of a type costs as much as the graph does.
        assert [operator for operator in plan_operators if _scans_the_graph(operator)] == []
