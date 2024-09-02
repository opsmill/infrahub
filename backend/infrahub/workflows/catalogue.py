from .models import WorkerPoolDefinition, WorkflowDefinition

WORKER_POOL = WorkerPoolDefinition(
    name="infrahub-internal", worker_type="infrahubasync", description="Pool for internal tasks"
)

WEBHOOK_SEND = WorkflowDefinition(
    name="webhook_send",
    work_pool=WORKER_POOL,
    module="infrahub.message_bus.operations.send.webhook",
    function="send_webhook",
)

TRANSFORM_JINJA2_RENDER = WorkflowDefinition(
    name="transform_render_jinja2_template",
    work_pool=WORKER_POOL,
    module="infrahub.message_bus.operations.transform.jinja",
    function="transform_render_jinja2_template",
)

ANONYMOUS_TELEMETRY_SEND = WorkflowDefinition(
    name="anonymous_telemetry_send",
    work_pool=WORKER_POOL,
    cron="0 2 * * *",
    module="infrahub.message_bus.operations.send.telemetry",
    function="send_telemetry_push",
)

DUMMY_FLOW = WorkflowDefinition(
    name="dummy_flow",
    work_pool=WORKER_POOL,
    module="infrahub.tasks.dummy",
    function="dummy_flow",
)

worker_pools = [WORKER_POOL]

workflows = [WEBHOOK_SEND, TRANSFORM_JINJA2_RENDER, ANONYMOUS_TELEMETRY_SEND, DUMMY_FLOW]
