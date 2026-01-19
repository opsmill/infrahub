from __future__ import annotations

from collections import Counter

import pytest

from infrahub.constants.environment import INSTALLATION_TYPE
from infrahub.workers.dependencies import get_installation_type
from infrahub.workflows import catalogue
from infrahub.workflows.catalogue import get_workflows
from infrahub.workflows.models import WorkflowDefinition


@pytest.mark.parametrize("workflow", [pytest.param(workflow, id=workflow.name) for workflow in get_workflows()])
def test_workflow_definition(workflow: WorkflowDefinition) -> None:
    """Validate that we can import the function for each workflow."""
    workflow.load_function()


@pytest.mark.parametrize("workflow", [pytest.param(workflow, id=workflow.name) for workflow in get_workflows()])
def test_workflow_definition_matches(workflow: WorkflowDefinition) -> None:
    """Validate that the name of the workflow matches the name of the flow"""
    flow = workflow.load_function()
    assert hasattr(flow, "name")
    assert workflow.name == flow.name


def test_workflow_definition_flow_names() -> None:
    """Validate that each workflow has a unique name defined"""
    flow_names = [workflow.name for workflow in get_workflows()]
    name_counter = Counter(flow_names)
    duplicates = [name for name, count in name_counter.items() if count > 1]
    assert not duplicates, f"Duplicate flow names found: {', '.join(duplicates)}"


def test_workflows_sorted() -> None:
    """
    Only test that workflows are defined in an alphabetical way for developer comfort.
    """

    if get_installation_type() != INSTALLATION_TYPE:
        return

    catalogue_attrs = [getattr(catalogue, name) for name in dir(catalogue)]
    ordered_workflows = [
        catalogue_attr for catalogue_attr in catalogue_attrs if isinstance(catalogue_attr, WorkflowDefinition)
    ]
    # Compare by name only since some workflows have dynamically generated cron schedules
    ordered_names = [w.name for w in ordered_workflows]
    workflow_names = [w.name for w in get_workflows()]
    assert ordered_names == workflow_names, "The list of workflows isn't sorted alphabetically"
