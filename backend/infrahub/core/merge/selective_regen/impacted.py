from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.regeneration.impact import get_field_level_impacted_subscribers
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer
from infrahub.graphql.execution import cached_parse

if TYPE_CHECKING:
    from infrahub_sdk.client import InfrahubClient
    from infrahub_sdk.diff import NodeDiff

    from infrahub.core.regeneration.models import TargetSelection
    from infrahub.graphql.analyzer import GraphQLQueryReport


class ImpactedSubscriberResolver:
    """Resolve the subscribers whose queried fields a diff changed.

    A seam rather than a translation: it holds the client and forwards, so a selector can be driven
    with a canned selection instead of a live query analysis and database.
    """

    def __init__(self, client: InfrahubClient) -> None:
        self.client = client

    def analyze(self, *, query_payload: str, target_branch: str) -> GraphQLQueryReport:
        """What the query reads, from its text analyzed against the target branch schema."""
        return InfrahubGraphQLQueryAnalyzer(
            query=query_payload,
            branch=registry.get_branch_from_registry(branch=target_branch),
            schema_branch=registry.schema.get_schema_branch(name=target_branch),
            document=cached_parse(query_payload),
        ).query_report

    async def resolve(
        self,
        *,
        query_report: GraphQLQueryReport,
        diff_summary: list[NodeDiff],
        target_branch: str,
        subscriber_kind: str,
        every_target: list[str],
    ) -> TargetSelection:
        return await get_field_level_impacted_subscribers(
            query_report=query_report,
            diff_summary=diff_summary,
            query_branch=target_branch,
            subscriber_kind=subscriber_kind,
            every_target=every_target,
            client=self.client,
        )
