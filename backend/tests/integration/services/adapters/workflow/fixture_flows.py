"""Test-only workflow definitions that dispatch each other through the worker adapter.

The parent/child/grandchild chain lets integration tests observe how the
priority stamped into the dispatched context routes descendant flow runs.
"""

from prefect import flow

from infrahub.context import InfrahubContext
from infrahub.services.adapters.workflow.worker import WorkflowWorkerExecution
from infrahub.tls.registry import TlsContextRegistry
from infrahub.workflows.constants import WorkflowPriority
from infrahub.workflows.models import WorkflowDefinition

FIXTURE_MODULE = "tests.integration.services.adapters.workflow.fixture_flows"

PRIORITY_GRANDCHILD = WorkflowDefinition(
    name="priority_fixture_grandchild",
    module=FIXTURE_MODULE,
    function="priority_grandchild",
)

PRIORITY_LEAF_HIGH_DEFAULT = WorkflowDefinition(
    name="priority_fixture_leaf_high_default",
    module=FIXTURE_MODULE,
    function="priority_leaf_high_default",
    default_priority=WorkflowPriority.HIGH,
)

PRIORITY_CHILD = WorkflowDefinition(
    name="priority_fixture_child",
    module=FIXTURE_MODULE,
    function="priority_child",
)

PRIORITY_PARENT = WorkflowDefinition(
    name="priority_fixture_parent",
    module=FIXTURE_MODULE,
    function="priority_parent",
)

PRIORITY_PARENT_HIGH_DEFAULT_CHILD = WorkflowDefinition(
    name="priority_fixture_parent_high_default_child",
    module=FIXTURE_MODULE,
    function="priority_parent_high_default_child",
)

PRIORITY_PARENT_OVERRIDING = WorkflowDefinition(
    name="priority_fixture_parent_overriding",
    module=FIXTURE_MODULE,
    function="priority_parent_overriding",
)

PRIORITY_PARENT_BLOCKING = WorkflowDefinition(
    name="priority_fixture_parent_blocking",
    module=FIXTURE_MODULE,
    function="priority_parent_blocking",
)

PRIORITY_FIXTURE_WORKFLOWS = [
    PRIORITY_GRANDCHILD,
    PRIORITY_LEAF_HIGH_DEFAULT,
    PRIORITY_CHILD,
    PRIORITY_PARENT,
    PRIORITY_PARENT_HIGH_DEFAULT_CHILD,
    PRIORITY_PARENT_OVERRIDING,
    PRIORITY_PARENT_BLOCKING,
]


@flow(name="priority-fixture-grandchild")
async def priority_grandchild(context: InfrahubContext) -> None:
    """Leaf of the fixture tree; dispatches nothing."""


@flow(name="priority-fixture-leaf-high-default")
async def priority_leaf_high_default(context: InfrahubContext) -> None:
    """Leaf registered with a high catalogue default; dispatches nothing."""


@flow(name="priority-fixture-child")
async def priority_child(context: InfrahubContext) -> None:
    service = WorkflowWorkerExecution(tls_registry=TlsContextRegistry())
    await service.submit_workflow(workflow=PRIORITY_GRANDCHILD, context=context)


@flow(name="priority-fixture-parent")
async def priority_parent(context: InfrahubContext) -> None:
    service = WorkflowWorkerExecution(tls_registry=TlsContextRegistry())
    await service.submit_workflow(workflow=PRIORITY_CHILD, context=context)


@flow(name="priority-fixture-parent-high-default-child")
async def priority_parent_high_default_child(context: InfrahubContext) -> None:
    service = WorkflowWorkerExecution(tls_registry=TlsContextRegistry())
    await service.submit_workflow(workflow=PRIORITY_LEAF_HIGH_DEFAULT, context=context)


@flow(name="priority-fixture-parent-overriding")
async def priority_parent_overriding(context: InfrahubContext) -> None:
    service = WorkflowWorkerExecution(tls_registry=TlsContextRegistry())
    await service.submit_workflow(workflow=PRIORITY_CHILD, context=context, priority=WorkflowPriority.LOW)


@flow(name="priority-fixture-parent-blocking")
async def priority_parent_blocking(context: InfrahubContext) -> None:
    """Dispatch the child through the blocking entry point and wait for its result."""
    service = WorkflowWorkerExecution(tls_registry=TlsContextRegistry())
    await service.execute_workflow(workflow=PRIORITY_GRANDCHILD, context=context)
