from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.workflows.catalogue import workflows

if TYPE_CHECKING:
    from infrahub.workflows.models import WorkflowDefinition


@pytest.mark.parametrize("workflow", [pytest.param(workflow, id=workflow.name) for workflow in workflows])
def test_workflow_definition(workflow: WorkflowDefinition) -> None:
    """Validate that we can import the function for each workflow."""
    workflow.validate_workflow()
