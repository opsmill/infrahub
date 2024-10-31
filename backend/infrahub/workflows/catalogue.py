from infrahub.core.constants import BranchSupportType

from .constants import WorkflowTag, WorkflowType
from .models import WorkerPoolDefinition, WorkflowDefinition

INFRAHUB_WORKER_POOL = WorkerPoolDefinition(
    name="infrahub-worker", worker_type="infrahubasync", description="Default Pool for internal tasks"
)

WEBHOOK_SEND = WorkflowDefinition(
    name="event-send-webhook",
    type=WorkflowType.USER,
    module="infrahub.send.webhook",
    function="send_webhook",
)

TRANSFORM_JINJA2_RENDER = WorkflowDefinition(
    name="transform_render_jinja2_template",
    type=WorkflowType.USER,
    module="infrahub.transformations.tasks",
    function="transform_render_jinja2_template",
    branch_support=BranchSupportType.AWARE,
)

TRANSFORM_PYTHON_RENDER = WorkflowDefinition(
    name="transform_render_python",
    type=WorkflowType.USER,
    module="infrahub.transformations.tasks",
    function="transform_python",
    branch_support=BranchSupportType.AWARE,
)

ANONYMOUS_TELEMETRY_SEND = WorkflowDefinition(
    name="anonymous_telemetry_send",
    type=WorkflowType.INTERNAL,
    cron="0 2 * * *",
    module="infrahub.tasks.telemetry",
    function="send_telemetry_push",
)

SCHEMA_APPLY_MIGRATION = WorkflowDefinition(
    name="schema_apply_migrations",
    type=WorkflowType.INTERNAL,
    module="infrahub.core.migrations.schema.tasks",
    function="schema_apply_migrations",
    branch_support=BranchSupportType.AWARE,
    tags=[WorkflowTag.DATABASE_CHANGE],
)

SCHEMA_VALIDATE_MIGRATION = WorkflowDefinition(
    name="schema_validate_migrations",
    type=WorkflowType.INTERNAL,
    module="infrahub.core.validators.tasks",
    function="schema_validate_migrations",
    branch_support=BranchSupportType.AWARE,
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
    branch_support=BranchSupportType.AWARE,
    tags=[WorkflowTag.DATABASE_CHANGE],
)

REQUEST_GENERATOR_RUN = WorkflowDefinition(
    name="generator-run",
    type=WorkflowType.INTERNAL,
    module="infrahub.generators.tasks",
    function="run_generator",
)

REQUEST_ARTIFACT_GENERATE = WorkflowDefinition(
    name="artifact-generate",
    type=WorkflowType.INTERNAL,
    module="infrahub.git.tasks",
    function="generate_artifact",
)

REQUEST_ARTIFACT_DEFINITION_GENERATE = WorkflowDefinition(
    name="request_artifact_definitions_generate",
    type=WorkflowType.INTERNAL,
    module="infrahub.git.tasks",
    function="generate_request_artifact_definition",
)

REQUEST_DIFF_UPDATE = WorkflowDefinition(
    name="diff-update",
    type=WorkflowType.INTERNAL,
    module="infrahub.core.diff.tasks",
    function="update_diff",
)

REQUEST_DIFF_REFRESH = WorkflowDefinition(
    name="diff-refresh",
    type=WorkflowType.INTERNAL,
    module="infrahub.core.diff.tasks",
    function="refresh_diff",
)

GIT_REPOSITORIES_SYNC = WorkflowDefinition(
    name="git_repositories_sync",
    type=WorkflowType.INTERNAL,
    cron="* * * * *",
    module="infrahub.git.tasks",
    function="sync_remote_repositories",
)

GIT_REPOSITORIES_CREATE_BRANCH = WorkflowDefinition(
    name="git_repositories_create_branch",
    type=WorkflowType.INTERNAL,
    module="infrahub.git.tasks",
    function="create_branch",
    branch_support=BranchSupportType.AWARE,
    tags=[WorkflowTag.DATABASE_CHANGE],
)
BRANCH_REBASE = WorkflowDefinition(
    name="branch-rebase",
    type=WorkflowType.INTERNAL,
    module="infrahub.core.branch.tasks",
    function="rebase_branch",
    branch_support=BranchSupportType.AWARE,
    tags=[WorkflowTag.DATABASE_CHANGE],
)

BRANCH_MERGE = WorkflowDefinition(
    name="branch-merge",
    type=WorkflowType.INTERNAL,
    module="infrahub.core.branch.tasks",
    function="merge_branch",
    branch_support=BranchSupportType.AWARE,
    tags=[WorkflowTag.DATABASE_CHANGE],
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
    BRANCH_MERGE,
    REQUEST_ARTIFACT_DEFINITION_GENERATE,
    REQUEST_GENERATOR_RUN,
    REQUEST_DIFF_UPDATE,
    REQUEST_DIFF_REFRESH,
]
