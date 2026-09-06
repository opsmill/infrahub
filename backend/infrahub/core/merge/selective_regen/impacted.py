from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrahub_sdk.diff import NodeDiff

    from infrahub.core.regeneration.impact import FieldLevelImpactResolver
    from infrahub.core.regeneration.models import TargetSelection


class ImpactedSubscriberResolver:
    """Resolve the subscribers whose queried fields a diff changed.

    A seam rather than a translation: it forwards to the shared resolver under the merge's branch
    vocabulary, so a selector can be driven with a canned selection instead of a live query analysis
    and database.
    """

    def __init__(self, resolver: FieldLevelImpactResolver) -> None:
        self.resolver = resolver

    async def resolve(
        self,
        *,
        query_payload: str,
        diff_summary: list[NodeDiff],
        target_branch: str,
        subscriber_kind: str,
        every_target: list[str],
    ) -> TargetSelection:
        return await self.resolver.resolve(
            query_payload=query_payload,
            diff_summary=diff_summary,
            query_branch=target_branch,
            subscriber_kind=subscriber_kind,
            every_target=every_target,
        )
