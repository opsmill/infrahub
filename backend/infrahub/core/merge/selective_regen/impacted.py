from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.proposed_change.tasks import ImpactScope, get_field_level_impacted_subscribers

if TYPE_CHECKING:
    from infrahub_sdk.client import InfrahubClient
    from infrahub_sdk.diff import NodeDiff

    from infrahub.proposed_change.tasks import ImpactedSubscribers


class ImpactedSubscriberResolver:
    """Resolve the subscriber ids whose queried fields changed, widened to all when unmappable."""

    def __init__(self, client: InfrahubClient) -> None:
        self.client = client

    async def resolve(
        self,
        *,
        query_payload: str,
        diff_summary: list[NodeDiff],
        target_branch: str,
        subscriber_kind: str,
        existing_subscribers: list[str],
    ) -> list[str]:
        impacted: ImpactedSubscribers = await get_field_level_impacted_subscribers(
            query_payload=query_payload,
            diff_summary=diff_summary,
            query_branch=target_branch,
            subscriber_kind=subscriber_kind,
            client=self.client,
        )
        if impacted.scope is ImpactScope.ALL:
            return existing_subscribers
        if impacted.scope is ImpactScope.NONE:
            return []
        return impacted.ids
