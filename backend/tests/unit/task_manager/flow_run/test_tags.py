from dataclasses import dataclass
from uuid import uuid4

import pytest
from prefect.client.schemas.objects import FlowRun

from infrahub.task_manager.flow_run.tags import WorkflowTagDecoder
from infrahub.workflows.constants import WorkflowTag, WorkflowType


def make_flow_run(tags: list[str]) -> FlowRun:
    return FlowRun(flow_id=uuid4(), name="run", tags=tags)


@dataclass
class BranchCase:
    name: str
    tags: list[str]
    expected: str | None


BRANCH_CASES = [
    BranchCase(
        name="single_branch_tag",
        tags=[WorkflowTag.BRANCH.render(identifier="main")],
        expected="main",
    ),
    BranchCase(
        name="branch_name_containing_a_slash",
        tags=[WorkflowTag.BRANCH.render(identifier="feature/login")],
        expected="feature/login",
    ),
    BranchCase(
        name="first_branch_tag_wins",
        tags=[
            WorkflowTag.BRANCH.render(identifier="first"),
            WorkflowTag.BRANCH.render(identifier="second"),
        ],
        expected="first",
    ),
    BranchCase(
        name="branch_resolved_among_other_tags",
        tags=[
            WorkflowTag.RELATED_NODE.render(identifier="abc"),
            WorkflowTag.BRANCH.render(identifier="main"),
            WorkflowTag.DATABASE_CHANGE.render(),
        ],
        expected="main",
    ),
    BranchCase(
        name="no_branch_tag",
        tags=[WorkflowTag.RELATED_NODE.render(identifier="abc"), WorkflowTag.DATABASE_CHANGE.render()],
        expected=None,
    ),
    BranchCase(name="no_tags", tags=[], expected=None),
]


@dataclass
class RelatedNodeCase:
    name: str
    tags: list[str]
    expected: list[str]


RELATED_NODE_CASES = [
    RelatedNodeCase(
        name="single_node",
        tags=[WorkflowTag.RELATED_NODE.render(identifier="node-1")],
        expected=["node-1"],
    ),
    RelatedNodeCase(
        name="multiple_nodes_keep_order",
        tags=[
            WorkflowTag.RELATED_NODE.render(identifier="node-2"),
            WorkflowTag.RELATED_NODE.render(identifier="node-1"),
        ],
        expected=["node-2", "node-1"],
    ),
    RelatedNodeCase(
        name="node_ids_filtered_from_other_tags",
        tags=[
            WorkflowTag.BRANCH.render(identifier="main"),
            WorkflowTag.RELATED_NODE.render(identifier="node-1"),
            WorkflowTag.DATABASE_CHANGE.render(),
        ],
        expected=["node-1"],
    ),
    RelatedNodeCase(
        name="no_node_tag",
        tags=[WorkflowTag.BRANCH.render(identifier="main")],
        expected=[],
    ),
    RelatedNodeCase(name="no_tags", tags=[], expected=[]),
]


@dataclass
class WorkflowTypeCase:
    name: str
    tags: list[str]
    expected: WorkflowType | None


WORKFLOW_TYPE_CASES = [
    WorkflowTypeCase(
        name="internal",
        tags=[WorkflowTag.WORKFLOWTYPE.render(identifier="internal")],
        expected=WorkflowType.INTERNAL,
    ),
    WorkflowTypeCase(
        name="core",
        tags=[WorkflowTag.WORKFLOWTYPE.render(identifier="core")],
        expected=WorkflowType.CORE,
    ),
    WorkflowTypeCase(
        name="type_resolved_among_other_tags",
        tags=[
            WorkflowTag.BRANCH.render(identifier="main"),
            WorkflowTag.WORKFLOWTYPE.render(identifier="user"),
            WorkflowTag.DATABASE_CHANGE.render(),
        ],
        expected=WorkflowType.USER,
    ),
    WorkflowTypeCase(
        name="unrecognised_value_is_not_an_error",
        tags=[WorkflowTag.WORKFLOWTYPE.render(identifier="something-else")],
        expected=None,
    ),
    WorkflowTypeCase(
        name="unrecognised_value_does_not_hide_a_valid_one",
        tags=[
            WorkflowTag.WORKFLOWTYPE.render(identifier="something-else"),
            WorkflowTag.WORKFLOWTYPE.render(identifier="internal"),
        ],
        expected=WorkflowType.INTERNAL,
    ),
    WorkflowTypeCase(
        name="no_type_tag",
        tags=[WorkflowTag.BRANCH.render(identifier="main")],
        expected=None,
    ),
    WorkflowTypeCase(name="no_tags", tags=[], expected=None),
]


class TestWorkflowTagDecoder:
    @pytest.mark.parametrize("case", WORKFLOW_TYPE_CASES, ids=[c.name for c in WORKFLOW_TYPE_CASES])
    def test_workflow_type(self, case: WorkflowTypeCase) -> None:
        assert WorkflowTagDecoder().workflow_type(make_flow_run(tags=case.tags)) == case.expected

    @pytest.mark.parametrize("case", BRANCH_CASES, ids=[c.name for c in BRANCH_CASES])
    def test_branch_name(self, case: BranchCase) -> None:
        assert WorkflowTagDecoder().branch_name(make_flow_run(tags=case.tags)) == case.expected

    @pytest.mark.parametrize("case", RELATED_NODE_CASES, ids=[c.name for c in RELATED_NODE_CASES])
    def test_related_node_ids(self, case: RelatedNodeCase) -> None:
        assert WorkflowTagDecoder().related_node_ids(make_flow_run(tags=case.tags)) == case.expected
