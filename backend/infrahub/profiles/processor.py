from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.log import get_logger

from .graphql_queries import ProfileNodeIDQuery
from .submission import submit_profile_refresh

if TYPE_CHECKING:
    from infrahub_sdk.client import InfrahubClient

    from infrahub.events.models import EventContext
    from infrahub.log import InfrahubLogger
    from infrahub.services.adapters.workflow import InfrahubWorkflow

    from .replay import NodeRefreshFilter


class ProfileRefreshProcessor:
    """Submit the profile refresh of the nodes and templates linked to a profile that the filter selects."""

    def __init__(
        self,
        client: InfrahubClient,
        workflow: InfrahubWorkflow,
        node_filter: NodeRefreshFilter,
        logger: InfrahubLogger | None = None,
    ) -> None:
        self.client = client
        self.workflow = workflow
        self.node_filter = node_filter
        self.log = logger or get_logger()

    async def run(self, branch_name: str, profile_id: str, peer_kinds: list[str], context: EventContext) -> None:
        """Read the linked nodes of each kind in pages, and submit the refresh of the nodes the filter selects."""
        for peer_kind in peer_kinds:
            node_query = ProfileNodeIDQuery(kind=peer_kind, profile_id=profile_id)
            submitted = 0
            held = 0
            async for page_ids in node_query.fetch_all_paginated(
                client=self.client, branch_name=branch_name, page_size=node_query.page_size
            ):
                node_ids = await self.node_filter.select(page_ids)
                if node_ids:
                    await submit_profile_refresh(
                        workflow=self.workflow,
                        branch_name=branch_name,
                        node_ids=node_ids,
                        context=context,
                        profile_id=profile_id,
                    )
                submitted += len(node_ids)
                held += len(page_ids) - len(node_ids)
            self.log.info(
                f"Submitted the profile refresh of {submitted} {peer_kind} node(s) for profile {profile_id},"
                f" {held} already held its values"
            )
