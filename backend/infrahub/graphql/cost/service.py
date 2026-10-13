from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.graphql.cost.estimator import estimate
from infrahub.graphql.cost.first_step import concrete_kinds_of
from infrahub.graphql.cost.tree import build_cost_tree

if TYPE_CHECKING:
    from graphql import GraphQLSchema

    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
    from infrahub.graphql.cost.first_step import FirstStepCounter
    from infrahub.graphql.cost.models import QueryEstimate
    from infrahub.graphql.cost.statistics_store import StatisticsSnapshotHolder, StatisticsStore


class QueryCostEstimator:
    """Estimate the cost of each field of a query on one branch and time."""

    def __init__(
        self,
        counter: FirstStepCounter,
        store: StatisticsStore,
        snapshot_holder: StatisticsSnapshotHolder,
        schema_branch: SchemaBranch,
        branch: Branch,
        reads_current_time: bool,
    ) -> None:
        """Prepare the estimates of the queries that read one branch at one time.

        Args:
            counter: Counts the first step on the branch and at the time the queries read.
            snapshot_holder: Statistics the process loaded last, shared by the requests of the process.
            reads_current_time: The queries read the current time rather than a time given with the request.

        """
        self.counter = counter
        self.store = store
        self.snapshot_holder = snapshot_holder
        self.schema_branch = schema_branch
        self.branch = branch
        self.reads_current_time = reads_current_time

    async def estimate(
        self, analyzer: InfrahubGraphQLQueryAnalyzer, schema: GraphQLSchema, variable_values: dict[str, Any] | None
    ) -> QueryEstimate:
        """Estimate each field of the query operation from the statistics.

        With variable values, even an empty mapping, the top-level fields and the fields directly under them
        are counted first; without them, only the current label counts of the kinds in the query are read.

        Raises:
            GraphQLError: When a variable value does not match the type the operation declares, or when the
                offset or the limit of a top-level field is negative.

        """
        tree = build_cost_tree(
            analyzer=analyzer, schema=schema, schema_branch=self.schema_branch, variable_values=variable_values
        )
        if variable_values is not None:
            first_step = await self.counter.count(tree=tree)
            label_counts = dict(first_step.label_counts)
        else:
            first_step = None
            label_counts = await self.counter.read_label_counts(kinds=concrete_kinds_of(tree=tree))

        snapshot = await self.snapshot_holder.get(store=self.store)
        return estimate(
            tree=tree,
            snapshot=snapshot,
            first_step=first_step,
            label_counts=label_counts,
            reads_main_now=self.reads_current_time
            and snapshot is not None
            and snapshot.pointer.branch == self.branch.name,
        )
