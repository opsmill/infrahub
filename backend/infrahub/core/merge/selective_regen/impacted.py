from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from infrahub_sdk.diff import NodeDiff

    from infrahub.core.regeneration.models import TargetSelection


class ImpactedSubscriberResolver(Protocol):
    """Resolve the subscribers whose queried fields a diff changed.

    A selector depends on this so it can be driven with a canned selection instead of a live query
    analysis and database.
    """

    async def resolve(
        self,
        *,
        query_payload: str,
        diff_summary: list[NodeDiff],
        query_branch: str,
        subscriber_kind: str,
        every_target: list[str],
    ) -> TargetSelection: ...
