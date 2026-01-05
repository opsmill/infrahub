from __future__ import annotations

from collections import Counter

import pytest

from infrahub.constants.environment import INSTALLATION_TYPE
from infrahub.workers.dependencies import get_installation_type
from infrahub.workflows import catalogue
from infrahub.workflows.catalogue import WORKER_POOLS, get_workflows
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
    for worker_pool in WORKER_POOLS:
        if worker_pool in ordered_workflows:
            ordered_workflows.remove(worker_pool)
    assert ordered_workflows == get_workflows(), "The list of workflows isn't sorted alphabetically"
