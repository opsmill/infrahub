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
    module="infrahub.transformations.tasks",
    function="transform_render_jinja2_template",
)

TRANSFORM_PYTHON_RENDER = WorkflowDefinition(
    name="transform_render_python",
    type=WorkflowType.USER,
    module="infrahub.transformations.tasks",
    function="transform_python",
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

TRIGGER_ARTIFACT_DEFINITION_GENERATE = WorkflowDefinition(
    name="artifact-definition-generate",
    type=WorkflowType.INTERNAL,
    module="infrahub.git.tasks",
    function="generate_artifact_definition",
)

IPAM_RECONCILIATION = WorkflowDefinition(
    name="ipam_reconciliation",
    type=WorkflowType.INTERNAL,
    module="infrahub.core.ipam.tasks",
    function="ipam_reconciliation",
)

REQUEST_ARTIFACT_GENERATE = WorkflowDefinition(
    name="artifact-generate",
    type=WorkflowType.INTERNAL,
    module="infrahub.git.tasks",
    function="generate_artifact",
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
BRANCH_REBASE = WorkflowDefinition(
    name="branch-rebase",
    type=WorkflowType.INTERNAL,
    module="infrahub.core.branch.tasks",
    function="rebase_branch",
)

worker_pools = [INFRAHUB_WORKER_POOL]

workflows = [
    WEBHOOK_SEND,
    TRANSFORM_JINJA2_RENDER,
    TRANSFORM_PYTHON_RENDER,
    ANONYMOUS_TELEMETRY_SEND,
    SCHEMA_APPLY_MIGRATION,
    SCHEMA_VALIDATE_MIGRATION,
    TRIGGER_ARTIFACT_DEFINITION_GENERATE,
    IPAM_RECONCILIATION,
    GIT_REPOSITORIES_SYNC,
    GIT_REPOSITORIES_CREATE_BRANCH,
    REQUEST_ARTIFACT_GENERATE,
    BRANCH_REBASE,
]
