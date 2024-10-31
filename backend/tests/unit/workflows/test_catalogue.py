from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

import pytest

from infrahub.workflows.catalogue import workflows

if TYPE_CHECKING:
    from infrahub.workflows.models import WorkflowDefinition


@pytest.mark.parametrize("workflow", [pytest.param(workflow, id=workflow.name) for workflow in workflows])
def test_workflow_definition(workflow: WorkflowDefinition) -> None:
    """Validate that we can import the function for each workflow."""
    workflow.validate_workflow()


@pytest.mark.parametrize("workflow", [pytest.param(workflow, id=workflow.name) for workflow in workflows])
def test_workflow_definition_matches(workflow: WorkflowDefinition) -> None:
    """Validate that the name of the workflow matches the name of the flow"""
    flow = workflow.get_function()
    assert hasattr(flow, "name")
    assert workflow.name == flow.name


def test_workflow_definition_flow_names() -> None:
    """Validate that each workflow has a unique name defined"""
    flow_names = [workflow.name for workflow in workflows]
    name_counter = Counter(flow_names)
    duplicates = [name for name, count in name_counter.items() if count > 1]
    assert not duplicates, f"Duplicate flow names found: {', '.join(duplicates)}"
