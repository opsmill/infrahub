from __future__ import annotations

from typing import TYPE_CHECKING, Any

from graphene import Field
from prefect.client.orchestration import get_client

from infrahub.graphql.types.scheduled_flow import ScheduledFlows
from infrahub.task_manager.scheduled_flow.service import build_scheduled_flow_service

if TYPE_CHECKING:
    from graphql import GraphQLResolveInfo

    from infrahub.task_manager.scheduled_flow.models import ScheduledFlowQueryResult, ScheduledFlowSummary


class ScheduledFlowConnectionSerializer:
    """Render scheduled-flow query results into the GraphQL connection shape."""

    def serialize(self, result: ScheduledFlowQueryResult) -> dict[str, Any]:
        return {
            "count": len(result.flows),
            "catalogue_only": result.catalogue_only,
            "edges": [{"node": self._serialize_node(flow)} for flow in result.flows],
        }

    def _serialize_node(self, flow: ScheduledFlowSummary) -> dict[str, Any]:
        latest_run = flow.latest_run
        return {
            "deployment_id": str(flow.deployment_id),
            "name": flow.name,
            "workflow_type": flow.workflow_type,
            "cron": flow.cron,
            "timezone": flow.timezone,
            "interval_seconds": flow.interval_seconds,
            "next_run_at": flow.next_run_at.isoformat() if flow.next_run_at else None,
            "active": flow.active,
            "concurrency_limit": flow.concurrency_limit,
            "collision_strategy": flow.collision_strategy,
            "latest_run": {
                "id": str(latest_run.id),
                "state": latest_run.state_type,
                "state_name": latest_run.state_name,
                "expected_start_time": (
                    latest_run.expected_start_time.isoformat() if latest_run.expected_start_time else None
                ),
                "start_time": latest_run.start_time.isoformat() if latest_run.start_time else None,
                "end_time": latest_run.end_time.isoformat() if latest_run.end_time else None,
            }
            if latest_run
            else None,
            "recent_outcomes": {
                "window_hours": flow.recent_outcomes.window_hours,
                "total": flow.recent_outcomes.total,
                "counts": [
                    {"state": state, "count": count} for state, count in sorted(flow.recent_outcomes.counts.items())
                ],
            },
            "health": flow.health,
            "deployment_created_at": (flow.deployment_created_at.isoformat() if flow.deployment_created_at else None),
        }


class ScheduledFlowsResolver:
    @staticmethod
    async def resolve(
        root: dict,  # noqa: ARG004
        info: GraphQLResolveInfo,  # noqa: ARG004
    ) -> dict[str, Any]:
        async with get_client(sync_client=False) as client:
            service = await build_scheduled_flow_service(client=client)
            result = await service.query()
        return ScheduledFlowConnectionSerializer().serialize(result=result)


InfrahubScheduledFlows = Field(
    ScheduledFlows,
    description="Every registered scheduled background flow with its schedule and recent run outcomes",
    resolver=ScheduledFlowsResolver.resolve,
    required=True,
)
