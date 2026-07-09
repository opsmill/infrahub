from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.context import InfrahubContext

if TYPE_CHECKING:
    from infrahub.events.models import EventContext
    from infrahub.workflows.constants import WorkflowPriority
    from infrahub.workflows.models import WorkflowDefinition


def resolve_priority(
    priority: WorkflowPriority | None,
    context: InfrahubContext | EventContext | None,
    workflow: WorkflowDefinition,
) -> WorkflowPriority:
    """Resolve the effective priority of a dispatch.

    Precedence is strict: the explicit argument wins, then the priority carried
    by a full execution context, then the workflow's catalogue default. The
    result is exact — never floored, capped, or combined with the catalogue
    default. Event contexts carry no priority and contribute nothing.
    """
    if priority is not None:
        return priority
    if isinstance(context, InfrahubContext) and context.priority is not None:
        return context.priority
    return workflow.default_priority


def prepare_dispatch(
    workflow: WorkflowDefinition,
    context: InfrahubContext | EventContext | None,
    priority: WorkflowPriority | None,
) -> tuple[InfrahubContext | EventContext | None, str | None]:
    """Prepare the context and queue routing of a single dispatch.

    Returns the context to hand to the child run and the work queue to route it
    to. A full execution context is returned as a copy stamped with the resolved
    effective priority — the caller's object is never mutated — so the whole
    task tree inherits the priority of its root. The queue name is only set when
    the explicit argument or the context supplied the priority; when only the
    catalogue default applies, no explicit routing is requested and the run
    lands on its deployment's default queue.
    """
    effective = resolve_priority(priority=priority, context=context, workflow=workflow)
    supplied = priority is not None or (isinstance(context, InfrahubContext) and context.priority is not None)
    work_queue_name = effective.queue_name if supplied else None
    if isinstance(context, InfrahubContext):
        return context.model_copy(update={"priority": effective}), work_queue_name
    return context, work_queue_name
