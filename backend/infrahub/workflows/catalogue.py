from .constants import WorkflowType
from .models import WorkerPoolDefinition, WorkflowDefinition

INFRAHUB_WORKER_POOL = WorkerPoolDefinition(
    name="infrahub-worker", worker_type="infrahubasync", description="Default Pool for internal tasks"
)

WEBHOOK_SEND = WorkflowDefinition(
    name="webhook_send",
    type=WorkflowType.USER,
    module="infrahub.message_bus.operations.send.webhook",
    function="send_webhook",
)

TRANSFORM_JINJA2_RENDER = WorkflowDefinition(
    name="transform_render_jinja2_template",
    type=WorkflowType.USER,
    module="infrahub.message_bus.operations.transform.jinja",
    function="transform_render_jinja2_template",
)

ANONYMOUS_TELEMETRY_SEND = WorkflowDefinition(
    name="anonymous_telemetry_send",
    type=WorkflowType.INTERNAL,
    cron="0 2 * * *",
    module="infrahub.message_bus.operations.send.telemetry",
    function="send_telemetry_push",
)

SCHEMA_APPLY_MIGRATION = WorkflowDefinition(
    name="schema_apply_migrations",
    type=WorkflowType.INTERNAL,
    module="infrahub.core.migrations.schema.tasks",
    function="schema_apply_migrations",
)

SCHEMA_VALIDATE_MIGRATION = WorkflowDefinition(
    name="schema_validate_migrations",
    type=WorkflowType.INTERNAL,
    module="infrahub.core.validators.tasks",
    function="schema_validate_migrations",
)

IPAM_RECONCILIATION = WorkflowDefinition(
    name="ipam_reconciliation",
    type=WorkflowType.INTERNAL,
    module="infrahub.core.ipam.tasks",
    function="ipam_reconciliation",
)

GIT_REPOSITORIES_SYNC = WorkflowDefinition(
    name="git_repositories_sync",
    type=WorkflowType.INTERNAL,
    cron="*/10 * * * *",
    module="infrahub.git.tasks",
    function="sync_remote_repositories",
)

GIT_REPOSITORIES_CREATE_BRANCH = WorkflowDefinition(
    name="git_repositories_create_branch",
    type=WorkflowType.INTERNAL,
    module="infrahub.git.tasks",
    function="create_branch",
)

PROCESS_COMPUTED_MACRO = WorkflowDefinition(
    name="process_computed_macro",
    type=WorkflowType.INTERNAL,
    module="infrahub.process.computed_attribute.tasks",
    function="process_macro",
)

worker_pools = [INFRAHUB_WORKER_POOL]

workflows = [
    WEBHOOK_SEND,
    TRANSFORM_JINJA2_RENDER,
    ANONYMOUS_TELEMETRY_SEND,
    SCHEMA_APPLY_MIGRATION,
    SCHEMA_VALIDATE_MIGRATION,
    IPAM_RECONCILIATION,
    GIT_REPOSITORIES_SYNC,
    GIT_REPOSITORIES_CREATE_BRANCH,
    PROCESS_COMPUTED_MACRO,
]
