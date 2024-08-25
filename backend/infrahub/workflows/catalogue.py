from .models import WorkflowDefinition

WORKER_POOL = "infrahub-internal"

WEBHOOK_SEND = WorkflowDefinition(
    name="webhook_send",
    work_pool_name=WORKER_POOL,
    module="infrahub.message_bus.operations.send.webhook",
    function="send_webhook",
)

TRANSFORM_JINJA2_RENDER = WorkflowDefinition(
    name="transform_render_jinja2_template",
    work_pool_name=WORKER_POOL,
    module="infrahub.message_bus.operations.transform.jinja",
    function="transform_render_jinja2_template",
)

worker_pools = [WORKER_POOL]

workflows = [WEBHOOK_SEND, TRANSFORM_JINJA2_RENDER]
