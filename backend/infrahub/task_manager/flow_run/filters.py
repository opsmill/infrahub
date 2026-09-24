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

from infrahub.exceptions import ValidationError
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
        flow_run_filter = FlowRunFilter(tags=self._build_tag_filter(criteria=criteria))

        if criteria.ids:
            flow_run_filter.id = FlowRunFilterId(any_=[self._to_uuid(id) for id in criteria.ids])
        if criteria.statuses:
            flow_run_filter.state = FlowRunFilterState(type=FlowRunFilterStateType(any_=criteria.statuses))
        if criteria.q:
            flow_run_filter.name = FlowRunFilterName(like_=criteria.q)

        return flow_run_filter

    @staticmethod
    def _build_tag_filter(criteria: FlowRunQueryCriteria) -> FlowRunFilterTags:
        """Scope a listing by tag, and leave a run addressed by its own id unscoped.

        Neither tag identifies an Infrahub run on its own. The namespace tag is stamped at run time
        on every non-internal workflow, including the subflows called in process — those start
        untagged and never pass through a deployment, so they carry no workflow-type tag at all.
        The workflow-type tag comes from the deployment, which is the only handle an internal run
        has. A listing picks one of the two scopes: the namespace by default, the requested types
        when a type is asked for. An id is already unambiguous, so a lookup that names one and asks
        for no particular type constrains no tag — requiring either shape would drop half the runs
        from the detail page.
        """
        filter_tags: list[str] = []
        if not criteria.workflow_types and not criteria.ids:
            filter_tags.append(TAG_NAMESPACE)

        if criteria.tags:
            filter_tags.extend(criteria.tags)
        if criteria.branch:
            filter_tags.append(WorkflowTag.BRANCH.render(identifier=criteria.branch))
        # Only one related node is supported for now; how (and whether) to support more is unresolved.
        if criteria.related_nodes:
            filter_tags.append(WorkflowTag.RELATED_NODE.render(identifier=criteria.related_nodes[0]))

        type_tags = (
            [
                WorkflowTag.WORKFLOWTYPE.render(identifier=workflow_type.value)
                for workflow_type in criteria.workflow_types
            ]
            if criteria.workflow_types
            else None
        )

        return FlowRunFilterTags(all_=filter_tags or None, any_=type_tags)

    @staticmethod
    def _to_uuid(value: str) -> UUID:
        try:
            return UUID(value)
        except ValueError as exc:
            raise ValidationError(input_value=f"'{value}' is not a valid task id") from exc
