from uuid import UUID

from prefect.client.schemas.objects import StateType

from infrahub.task_manager.flow_run.filters import FlowRunFilterBuilder
from infrahub.task_manager.flow_run.models import FlowRunQueryCriteria
from infrahub.workflows.constants import TAG_NAMESPACE


class TestBuildFlowFilter:
    def test_no_workflows_leaves_name_unset(self) -> None:
        flow_filter = FlowRunFilterBuilder().build_flow_filter()

        assert flow_filter.name is None

    def test_workflows_set_name_any(self) -> None:
        flow_filter = FlowRunFilterBuilder().build_flow_filter(workflows=["flow_a", "flow_b"])

        assert flow_filter.name is not None
        assert flow_filter.name.any_ == ["flow_a", "flow_b"]


class TestBuildFlowRunFilter:
    def test_empty_criteria_only_scopes_to_namespace(self) -> None:
        flow_run_filter = FlowRunFilterBuilder().build_flow_run_filter(criteria=FlowRunQueryCriteria())

        assert flow_run_filter.tags is not None
        assert flow_run_filter.tags.all_ == [TAG_NAMESPACE]
        assert flow_run_filter.id is None
        assert flow_run_filter.state is None
        assert flow_run_filter.name is None

    def test_branch_appends_branch_tag(self) -> None:
        flow_run_filter = FlowRunFilterBuilder().build_flow_run_filter(criteria=FlowRunQueryCriteria(branch="main"))

        assert flow_run_filter.tags is not None
        assert flow_run_filter.tags.all_ == [TAG_NAMESPACE, "infrahub.app/branch/main"]

    def test_extra_tags_are_preserved(self) -> None:
        flow_run_filter = FlowRunFilterBuilder().build_flow_run_filter(
            criteria=FlowRunQueryCriteria(tags=["custom-a", "custom-b"])
        )

        assert flow_run_filter.tags is not None
        assert flow_run_filter.tags.all_ == [TAG_NAMESPACE, "custom-a", "custom-b"]

    def test_only_the_first_related_node_is_used(self) -> None:
        flow_run_filter = FlowRunFilterBuilder().build_flow_run_filter(
            criteria=FlowRunQueryCriteria(related_nodes=["node-1", "node-2"])
        )

        assert flow_run_filter.tags is not None
        assert flow_run_filter.tags.all_ == [TAG_NAMESPACE, "infrahub.app/node/node-1"]

    def test_ids_are_converted_to_uuid(self) -> None:
        id_a = "00000000-0000-0000-0000-000000000001"
        id_b = "00000000-0000-0000-0000-000000000002"

        flow_run_filter = FlowRunFilterBuilder().build_flow_run_filter(criteria=FlowRunQueryCriteria(ids=[id_a, id_b]))

        assert flow_run_filter.id is not None
        assert flow_run_filter.id.any_ == [UUID(id_a), UUID(id_b)]

    def test_statuses_set_state_type_any(self) -> None:
        flow_run_filter = FlowRunFilterBuilder().build_flow_run_filter(
            criteria=FlowRunQueryCriteria(statuses=[StateType.RUNNING, StateType.FAILED])
        )

        assert flow_run_filter.state is not None
        assert flow_run_filter.state.type is not None
        assert flow_run_filter.state.type.any_ == [StateType.RUNNING, StateType.FAILED]

    def test_q_sets_name_like(self) -> None:
        flow_run_filter = FlowRunFilterBuilder().build_flow_run_filter(criteria=FlowRunQueryCriteria(q="deploy"))

        assert flow_run_filter.name is not None
        assert flow_run_filter.name.like_ == "deploy"

    def test_all_criteria_combine(self) -> None:
        node_id = "00000000-0000-0000-0000-000000000003"
        flow_run_filter = FlowRunFilterBuilder().build_flow_run_filter(
            criteria=FlowRunQueryCriteria(
                tags=["custom"],
                branch="main",
                related_nodes=["rel-1"],
                ids=[node_id],
                statuses=[StateType.COMPLETED],
                q="deploy",
            )
        )

        assert flow_run_filter.tags is not None
        assert flow_run_filter.tags.all_ == [
            TAG_NAMESPACE,
            "custom",
            "infrahub.app/branch/main",
            "infrahub.app/node/rel-1",
        ]
        assert flow_run_filter.id is not None
        assert flow_run_filter.id.any_ == [UUID(node_id)]
        assert flow_run_filter.state is not None
        assert flow_run_filter.state.type is not None
        assert flow_run_filter.state.type.any_ == [StateType.COMPLETED]
        assert flow_run_filter.name is not None
        assert flow_run_filter.name.like_ == "deploy"
