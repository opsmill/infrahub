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
    module="infrahub.tasks.telemetry",
    function="send_telemetry_push",
)

SCHEMA_APPLY_MIGRATION = WorkflowDefinition(
    name="schema_apply_migrations",
    type=WorkflowType.INTERNAL,
    module="infrahub.core.migrations.schema.tasks",
    function="schema_apply_migrations",
    tags=[WorkflowTag.DATABASE_CHANGE],
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

TRIGGER_GENERATOR_DEFINITION_RUN = WorkflowDefinition(
    name="generator_definition_run",
    type=WorkflowType.INTERNAL,
    module="infrahub.generators.tasks",
    function="run_generator_definition",
)

IPAM_RECONCILIATION = WorkflowDefinition(
    name="ipam_reconciliation",
    type=WorkflowType.INTERNAL,
    module="infrahub.core.ipam.tasks",
    function="ipam_reconciliation",
    tags=[WorkflowTag.DATABASE_CHANGE],
)

REQUEST_GENERATOR_RUN = WorkflowDefinition(
    name="generator-run",
    type=WorkflowType.INTERNAL,
    module="infrahub.generators.tasks",
    function="run_generator",
)

REQUEST_GENERATOR_DEFINITION_RUN = WorkflowDefinition(
    name="request_generator_definition_run",
    type=WorkflowType.INTERNAL,
    module="infrahub.generators.tasks",
    function="request_generator_definition_run",
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
    tags=[WorkflowTag.DATABASE_CHANGE],
)

GIT_REPOSITORY_ADD = WorkflowDefinition(
    name="git-repository-add-read-write",
    type=WorkflowType.INTERNAL,
    module="infrahub.git.tasks",
    function="add_git_repository",
    tags=[WorkflowTag.DATABASE_CHANGE],
)

GIT_REPOSITORY_ADD_READ_ONLY = WorkflowDefinition(
    name="git-repository-add-read-only",
    type=WorkflowType.INTERNAL,
    module="infrahub.git.tasks",
    function="add_git_repository_read_only",
    tags=[WorkflowTag.DATABASE_CHANGE],
)

GIT_REPOSITORIES_PULL_READ_ONLY = WorkflowDefinition(
    name="git-repository-pull-read-only",
    type=WorkflowType.INTERNAL,
    module="infrahub.git.tasks",
    function="pull_read_only",
)

GIT_REPOSITORIES_MERGE = WorkflowDefinition(
    name="git-repository-merge",
    type=WorkflowType.INTERNAL,
    module="infrahub.git.tasks",
    function="merge_git_repository",
    tags=[WorkflowTag.DATABASE_CHANGE],
)

BRANCH_REBASE = WorkflowDefinition(
    name="branch-rebase",
    type=WorkflowType.INTERNAL,
    module="infrahub.core.branch.tasks",
    function="rebase_branch",
    tags=[WorkflowTag.DATABASE_CHANGE],
)

BRANCH_MERGE = WorkflowDefinition(
    name="branch-merge",
    type=WorkflowType.INTERNAL,
    module="infrahub.core.branch.tasks",
    function="merge_branch",
    tags=[WorkflowTag.DATABASE_CHANGE],
)

BRANCH_MERGE_MUTATION = WorkflowDefinition(
    name="merge-branch-mutation",
    type=WorkflowType.INTERNAL,
    module="infrahub.graphql.mutations.tasks",
    function="merge_branch_mutation",
    tags=[WorkflowTag.DATABASE_CHANGE],
)

BRANCH_DELETE = WorkflowDefinition(
    name="branch-delete",
    type=WorkflowType.INTERNAL,
    module="infrahub.core.branch.tasks",
    function="delete_branch",
)

BRANCH_VALIDATE = WorkflowDefinition(
    name="branch-validate",
    type=WorkflowType.INTERNAL,
    module="infrahub.core.branch.tasks",
    function="validate_branch",
)

BRANCH_CANCEL_PROPOSED_CHANGES = WorkflowDefinition(
    name="proposed-changes-cancel-branch",
    type=WorkflowType.INTERNAL,
    module="infrahub.proposed_change.tasks",
    function="cancel_proposed_changes_branch",
)

PROPOSED_CHANGE_MERGE = WorkflowDefinition(
    name="proposed-change-merge",
    type=WorkflowType.INTERNAL,
    module="infrahub.proposed_change.tasks",
    function="merge_proposed_change",
)

UPDATE_GRAPHQL_QUERY_GROUP = WorkflowDefinition(
    name="update_graphql_query_group",
    type=WorkflowType.INTERNAL,
    module="infrahub.groups.tasks",
    function="update_graphql_query_group",
)

PROCESS_COMPUTED_MACRO = WorkflowDefinition(
    name="process_computed_attribute_jinja2",
    type=WorkflowType.INTERNAL,
    module="infrahub.computed_attribute.tasks",
    function="process_jinja2",
)

COMPUTED_ATTRIBUTE_SETUP = WorkflowDefinition(
    name="computed-attribute-setup",
    type=WorkflowType.INTERNAL,
    module="infrahub.computed_attribute.tasks",
    function="computed_attribute_setup",
)

COMPUTED_ATTRIBUTE_SETUP_PYTHON = WorkflowDefinition(
    name="computed-attribute-setup-python",
    type=WorkflowType.INTERNAL,
    module="infrahub.computed_attribute.tasks",
    function="computed_attribute_setup_python",
)


UPDATE_COMPUTED_ATTRIBUTE_TRANSFORM = WorkflowDefinition(
    name="process_computed_attribute_transform",
    type=WorkflowType.INTERNAL,
    module="infrahub.computed_attribute.tasks",
    function="process_transform",
)

REQUEST_PROPOSED_CHANGE_DATA_INTEGRITY = WorkflowDefinition(
    name="proposed-changed-data-integrity",
    type=WorkflowType.INTERNAL,
    module="infrahub.proposed_change.tasks",
    function="run_proposed_change_data_integrity_check",
)

AUTOMATION_SCHEMA_UPDATED = WorkflowDefinition(
    name="schema-updated-setup",
    type=WorkflowType.INTERNAL,
    module="infrahub.schema.tasks",
    function="schema_updated_setup",
)

AUTOMATION_GIT_UPDATED = WorkflowDefinition(
    name="git-commit-automation-setup",
    type=WorkflowType.INTERNAL,
    module="infrahub.git.tasks",
    function="setup_commit_automation",
)


worker_pools = [INFRAHUB_WORKER_POOL]

workflows = [
    AUTOMATION_GIT_UPDATED,
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
    BRANCH_DELETE,
    BRANCH_VALIDATE,
    BRANCH_MERGE_MUTATION,
    REQUEST_ARTIFACT_DEFINITION_GENERATE,
    REQUEST_GENERATOR_RUN,
    REQUEST_DIFF_UPDATE,
    REQUEST_DIFF_REFRESH,
    GIT_REPOSITORIES_PULL_READ_ONLY,
    GIT_REPOSITORIES_MERGE,
    TRIGGER_GENERATOR_DEFINITION_RUN,
    BRANCH_CANCEL_PROPOSED_CHANGES,
    PROPOSED_CHANGE_MERGE,
    REQUEST_GENERATOR_DEFINITION_RUN,
    UPDATE_GRAPHQL_QUERY_GROUP,
    GIT_REPOSITORY_ADD,
    GIT_REPOSITORY_ADD_READ_ONLY,
    PROCESS_COMPUTED_MACRO,
    COMPUTED_ATTRIBUTE_SETUP,
    COMPUTED_ATTRIBUTE_SETUP_PYTHON,
    UPDATE_COMPUTED_ATTRIBUTE_TRANSFORM,
    REQUEST_PROPOSED_CHANGE_DATA_INTEGRITY,
    AUTOMATION_SCHEMA_UPDATED,
]

automation_setup_workflows = [AUTOMATION_GIT_UPDATED, AUTOMATION_SCHEMA_UPDATED]
