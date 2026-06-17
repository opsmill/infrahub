from uuid import UUID

from prefect.client.schemas.filters import (
    FlowFilter,
    FlowFilterName,
    FlowRunFilter,
    FlowRunFilterId,
    FlowRunFilterName,
    FlowRunFilterState,
    FlowRunFilterStateType,
    FlowRunFilterTags,
)

from infrahub.workflows.constants import TAG_NAMESPACE, WorkflowTag

from .models import FlowRunQueryCriteria


class FlowRunFilterBuilder:
    """Translate selection criteria into the filter objects understood by Prefect."""

    def build_flow_filter(self, workflows: list[str] | None = None) -> FlowFilter:
        flow_filter = FlowFilter()
        if workflows:
            flow_filter.name = FlowFilterName(any_=workflows)
        return flow_filter

    def build_flow_run_filter(self, criteria: FlowRunQueryCriteria) -> FlowRunFilter:
        filter_tags = [TAG_NAMESPACE]

        if criteria.tags:
            filter_tags.extend(criteria.tags)
        if criteria.branch:
            filter_tags.append(WorkflowTag.BRANCH.render(identifier=criteria.branch))
        # Only one related node is supported for now; how (and whether) to support more is unresolved.
        if criteria.related_nodes:
            filter_tags.append(WorkflowTag.RELATED_NODE.render(identifier=criteria.related_nodes[0]))

        flow_run_filter = FlowRunFilter(tags=FlowRunFilterTags(all_=filter_tags))

        if criteria.ids:
            flow_run_filter.id = FlowRunFilterId(any_=[UUID(id) for id in criteria.ids])
        if criteria.statuses:
            flow_run_filter.state = FlowRunFilterState(type=FlowRunFilterStateType(any_=criteria.statuses))
        if criteria.q:
            flow_run_filter.name = FlowRunFilterName(like_=criteria.q)

        return flow_run_filter
