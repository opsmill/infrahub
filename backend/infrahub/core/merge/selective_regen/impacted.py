from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.regeneration.impact import get_field_level_impacted_subscribers

if TYPE_CHECKING:
    from infrahub_sdk.client import InfrahubClient
    from infrahub_sdk.diff import NodeDiff

    from infrahub.core.regeneration.models import TargetSelection


class ImpactedSubscriberResolver:
    """Resolve the subscribers whose queried fields a diff changed.

    A seam rather than a translation: it holds the client and forwards, so a selector can be driven
    with a canned selection instead of a live query analysis and database.
    """

    def __init__(self, client: InfrahubClient) -> None:
        self.client = client

    async def resolve(
        self,
        *,
        query_payload: str,
        diff_summary: list[NodeDiff],
        target_branch: str,
        subscriber_kind: str,
        every_target: list[str],
    ) -> TargetSelection:
        return await get_field_level_impacted_subscribers(
            query_payload=query_payload,
            diff_summary=diff_summary,
            query_branch=target_branch,
            subscriber_kind=subscriber_kind,
            every_target=every_target,
            client=self.client,
        )
