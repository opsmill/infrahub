from graphene import Boolean, Enum, Field, Int, List, NonNull, ObjectType, String

from infrahub.task_manager.scheduled_flow.models import ScheduledFlowHealth

from .task import TaskState, WorkflowTypeEnum

ScheduledFlowHealthEnum = Enum.from_enum(
    ScheduledFlowHealth, name="ScheduledFlowHealthEnum", description="How a scheduled flow is currently faring"
)


class ScheduledFlowLatestRun(ObjectType):
    id = String(required=True)
    state = TaskState(required=False)
    state_name = String(required=False)
    expected_start_time = String(required=False)
    start_time = String(required=False, description="Null for a run cancelled by a collision before it began")
    end_time = String(required=False)


class ScheduledFlowOutcomeCount(ObjectType):
    state = TaskState(required=True)
    count = Int(required=True)


class ScheduledFlowOutcomes(ObjectType):
    window_hours = Int(required=True)
    total = Int(required=True)
    counts = List(NonNull(ScheduledFlowOutcomeCount), required=True)


class ScheduledFlow(ObjectType):
    deployment_id = String(required=True)
    name = String(required=True)
    workflow_type = WorkflowTypeEnum(
        required=False, description="Null when the deployment carries no Infrahub workflow-type tag"
    )
    cron = String(required=True)
    timezone = String(required=False)
    interval_seconds = Int(
        required=False, description="Seconds between consecutive fire times; null when it cannot be derived"
    )
    next_run_at = String(required=False)
    active = Boolean(required=True, description="False when the schedule or the deployment itself is paused")
    concurrency_limit = Int(required=False)
    collision_strategy = String(required=False, description="Explains a CANCELLED verdict")
    latest_run = Field(
        ScheduledFlowLatestRun,
        required=False,
        description="The newest run that was due by now and got past the queue; never a future scheduled run",
    )
    recent_outcomes = Field(ScheduledFlowOutcomes, required=True)
    health = ScheduledFlowHealthEnum(required=True)
    deployment_created_at = String(required=False)


class ScheduledFlowNode(ObjectType):
    node = Field(ScheduledFlow, required=True)


class ScheduledFlows(ObjectType):
    edges = List(NonNull(ScheduledFlowNode), required=True, description="Ordered unhealthy-first, then by name")
    count = Int(required=True)
    catalogue_only = List(
        NonNull(String),
        required=True,
        description="Catalogue workflows that declare a cron but have no registered deployment",
    )
