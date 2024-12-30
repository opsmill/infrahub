import random

from .constants import WorkflowTag, WorkflowType
from .models import WorkerPoolDefinition, WorkflowDefinition

INFRAHUB_WORKER_POOL = WorkerPoolDefinition(name="infrahub-worker", description="Default Pool for internal tasks")

WEBHOOK_SEND = WorkflowDefinition(
    name="event-send-webhook",
    type=WorkflowType.USER,
    module="infrahub.webhook.tasks",
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
    cron=f"{random.randint(0, 59)} 2 * * *",
    module="infrahub.tasks.telemetry",
    function="send_telemetry_push",
)

SCHEMA_APPLY_MIGRATION = WorkflowDefinition(
    name="schema_apply_migrations",
    type=WorkflowType.CORE,
    module="infrahub.core.migrations.schema.tasks",
    function="schema_apply_migrations",
    tags=[WorkflowTag.DATABASE_CHANGE],
)

SCHEMA_VALIDATE_MIGRATION = WorkflowDefinition(
    name="schema_validate_migrations",
    type=WorkflowType.CORE,
    module="infrahub.core.validators.tasks",
    function="schema_validate_migrations",
)

TRIGGER_ARTIFACT_DEFINITION_GENERATE = WorkflowDefinition(
    name="artifact-definition-generate",
    type=WorkflowType.CORE,
    module="infrahub.git.tasks",
    function="generate_artifact_definition",
)

TRIGGER_GENERATOR_DEFINITION_RUN = WorkflowDefinition(
    name="generator_definition_run",
    type=WorkflowType.CORE,
    module="infrahub.generators.tasks",
    function="run_generator_definition",
    tags=[WorkflowTag.DATABASE_CHANGE],
)

IPAM_RECONCILIATION = WorkflowDefinition(
    name="ipam_reconciliation",
    type=WorkflowType.CORE,
    module="infrahub.core.ipam.tasks",
    function="ipam_reconciliation",
    tags=[WorkflowTag.DATABASE_CHANGE],
)

REQUEST_GENERATOR_RUN = WorkflowDefinition(
    name="generator-run",
    type=WorkflowType.USER,
    module="infrahub.generators.tasks",
    function="run_generator",
    tags=[WorkflowTag.DATABASE_CHANGE],
)

REQUEST_GENERATOR_DEFINITION_RUN = WorkflowDefinition(
    name="request_generator_definition_run",
    type=WorkflowType.CORE,
    module="infrahub.generators.tasks",
    function="request_generator_definition_run",
    tags=[WorkflowTag.DATABASE_CHANGE],
)

REQUEST_ARTIFACT_GENERATE = WorkflowDefinition(
    name="artifact-generate",
    type=WorkflowType.CORE,  # NOTE need to check
    module="infrahub.git.tasks",
    function="generate_artifact",
    tags=[WorkflowTag.DATABASE_CHANGE],
)

REQUEST_ARTIFACT_DEFINITION_GENERATE = WorkflowDefinition(
    name="request_artifact_definitions_generate",
    type=WorkflowType.CORE,
    module="infrahub.git.tasks",
    function="generate_request_artifact_definition",
    tags=[WorkflowTag.DATABASE_CHANGE],
)

DIFF_UPDATE = WorkflowDefinition(
    name="diff-update",
    type=WorkflowType.CORE,
    module="infrahub.core.diff.tasks",
    function="update_diff",
)

DIFF_REFRESH = WorkflowDefinition(
    name="diff-refresh",
    type=WorkflowType.CORE,
    module="infrahub.core.diff.tasks",
    function="refresh_diff",
)

DIFF_REFRESH_ALL = WorkflowDefinition(
    name="diff-refresh-all",
    type=WorkflowType.INTERNAL,
    module="infrahub.core.diff.tasks",
    function="refresh_diff_all",
)

GIT_REPOSITORIES_SYNC = WorkflowDefinition(
    name="git_repositories_sync",
    type=WorkflowType.INTERNAL,
    cron="* * * * *",
    module="infrahub.git.tasks",
    function="sync_remote_repositories",
)

GIT_REPOSITORIES_CREATE_BRANCH = WorkflowDefinition(
    name="git-repositories-create-branch",
    type=WorkflowType.CORE,
    module="infrahub.git.tasks",
    function="create_branch",
    tags=[WorkflowTag.DATABASE_CHANGE],
)

GIT_REPOSITORY_ADD = WorkflowDefinition(
    name="git-repository-add-read-write",
    type=WorkflowType.CORE,
    module="infrahub.git.tasks",
    function="add_git_repository",
    tags=[WorkflowTag.DATABASE_CHANGE],
)

GIT_REPOSITORY_ADD_READ_ONLY = WorkflowDefinition(
    name="git-repository-add-read-only",
    type=WorkflowType.CORE,
    module="infrahub.git.tasks",
    function="add_git_repository_read_only",
    tags=[WorkflowTag.DATABASE_CHANGE],
)

GIT_REPOSITORIES_PULL_READ_ONLY = WorkflowDefinition(
    name="git-repository-pull-read-only",
    type=WorkflowType.CORE,
    module="infrahub.git.tasks",
    function="pull_read_only",
)

GIT_REPOSITORIES_MERGE = WorkflowDefinition(
    name="git-repository-merge",
    type=WorkflowType.CORE,
    module="infrahub.git.tasks",
    function="merge_git_repository",
    tags=[WorkflowTag.DATABASE_CHANGE],
)

BRANCH_REBASE = WorkflowDefinition(
    name="branch-rebase",
    type=WorkflowType.CORE,
    module="infrahub.core.branch.tasks",
    function="rebase_branch",
    tags=[WorkflowTag.DATABASE_CHANGE],
)

BRANCH_CREATE = WorkflowDefinition(
    name="create-branch",
    type=WorkflowType.CORE,
    module="infrahub.core.branch.tasks",
    function="create_branch",
    tags=[WorkflowTag.DATABASE_CHANGE],
)

BRANCH_MERGE = WorkflowDefinition(
    name="branch-merge",
    type=WorkflowType.CORE,
    module="infrahub.core.branch.tasks",
    function="merge_branch",
    tags=[WorkflowTag.DATABASE_CHANGE],
)

BRANCH_MERGE_MUTATION = WorkflowDefinition(
    name="merge-branch-mutation",
    type=WorkflowType.CORE,
    module="infrahub.graphql.mutations.tasks",
    function="merge_branch_mutation",
    tags=[WorkflowTag.DATABASE_CHANGE],
)

BRANCH_DELETE = WorkflowDefinition(
    name="branch-delete",
    type=WorkflowType.CORE,
    module="infrahub.core.branch.tasks",
    function="delete_branch",
)

BRANCH_VALIDATE = WorkflowDefinition(
    name="branch-validate",
    type=WorkflowType.CORE,
    module="infrahub.core.branch.tasks",
    function="validate_branch",
)

BRANCH_CANCEL_PROPOSED_CHANGES = WorkflowDefinition(
    name="proposed-changes-cancel-branch",
    type=WorkflowType.CORE,
    module="infrahub.proposed_change.tasks",
    function="cancel_proposed_changes_branch",
)

PROPOSED_CHANGE_MERGE = WorkflowDefinition(
    name="proposed-change-merge",
    type=WorkflowType.CORE,
    module="infrahub.proposed_change.tasks",
    function="merge_proposed_change",
    tags=[WorkflowTag.DATABASE_CHANGE],
)

GRAPHQL_QUERY_GROUP_UPDATE = WorkflowDefinition(
    name="graphql-query-group-update",
    type=WorkflowType.CORE,
    module="infrahub.groups.tasks",
    function="update_graphql_query_group",
)

PROCESS_COMPUTED_MACRO = WorkflowDefinition(
    name="process_computed_attribute_jinja2",
    type=WorkflowType.CORE,
    module="infrahub.computed_attribute.tasks",
    function="process_jinja2",
    tags=[WorkflowTag.DATABASE_CHANGE],
)

TRIGGER_UPDATE_JINJA_COMPUTED_ATTRIBUTES = WorkflowDefinition(
    name="trigger_update_jinja2_computed_attributes",
    type=WorkflowType.CORE,
    module="infrahub.computed_attribute.tasks",
    function="trigger_update_jinja2_computed_attributes",
)

TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES = WorkflowDefinition(
    name="trigger_update_python_computed_attributes",
    type=WorkflowType.CORE,
    module="infrahub.computed_attribute.tasks",
    function="trigger_update_python_computed_attributes",
)

COMPUTED_ATTRIBUTE_SETUP = WorkflowDefinition(
    name="computed-attribute-setup",
    type=WorkflowType.CORE,
    module="infrahub.computed_attribute.tasks",
    function="computed_attribute_setup",
)

COMPUTED_ATTRIBUTE_SETUP_PYTHON = WorkflowDefinition(
    name="computed-attribute-setup-python",
    type=WorkflowType.CORE,
    module="infrahub.computed_attribute.tasks",
    function="computed_attribute_setup_python",
)

COMPUTED_ATTRIBUTE_REMOVE_PYTHON = WorkflowDefinition(
    name="computed-attribute-remove-python",
    type=WorkflowType.CORE,
    module="infrahub.computed_attribute.tasks",
    function="computed_attribute_remove_python",
)

UPDATE_COMPUTED_ATTRIBUTE_TRANSFORM = WorkflowDefinition(
    name="process_computed_attribute_transform",
    type=WorkflowType.USER,
    module="infrahub.computed_attribute.tasks",
    function="process_transform",
    tags=[WorkflowTag.DATABASE_CHANGE],
)

QUERY_COMPUTED_ATTRIBUTE_TRANSFORM_TARGETS = WorkflowDefinition(
    name="query-computed-attribute-transform-targets",
    type=WorkflowType.CORE,
    module="infrahub.computed_attribute.tasks",
    function="query_transform_targets",
)

REQUEST_PROPOSED_CHANGE_DATA_INTEGRITY = WorkflowDefinition(
    name="proposed-changed-data-integrity",
    type=WorkflowType.CORE,
    module="infrahub.proposed_change.tasks",
    function="run_proposed_change_data_integrity_check",
)

REQUEST_PROPOSED_CHANGE_SCHEMA_INTEGRITY = WorkflowDefinition(
    name="proposed-changed-schema-integrity",
    type=WorkflowType.CORE,
    module="infrahub.proposed_change.tasks",
    function="run_proposed_change_schema_integrity_check",
)

REQUEST_PROPOSED_CHANGE_USER_TESTS = WorkflowDefinition(
    name="proposed-changed-user-tests",
    type=WorkflowType.USER,
    module="infrahub.proposed_change.tasks",
    function="run_proposed_change_user_tests",
)

AUTOMATION_BRANCH_ACTIONS = WorkflowDefinition(
    name="branch-actions-setup",
    type=WorkflowType.CORE,
    module="infrahub.core.branch.tasks",
    function="branch_actions_setup",
)

AUTOMATION_SCHEMA_UPDATED = WorkflowDefinition(
    name="schema-updated-setup",
    type=WorkflowType.CORE,
    module="infrahub.schema.tasks",
    function="schema_updated_setup",
)

AUTOMATION_GIT_UPDATED = WorkflowDefinition(
    name="git-commit-automation-setup",
    type=WorkflowType.CORE,
    module="infrahub.git.tasks",
    function="setup_commit_automation",
)

GIT_REPOSITORIES_DIFF_NAMES_ONLY = WorkflowDefinition(
    name="git-repository-diff-names-only",
    type=WorkflowType.INTERNAL,
    module="infrahub.git.tasks",
    function="git_repository_diff_names_only",
)

GIT_REPOSITORIES_IMPORT_OBJECTS = WorkflowDefinition(
    name="git-repository-import-object",
    type=WorkflowType.USER,
    module="infrahub.git.tasks",
    function="import_objects_from_git_repository",
    tags=[WorkflowTag.DATABASE_CHANGE],
)

REQUEST_PROPOSED_CHANGE_RUN_GENERATORS = WorkflowDefinition(
    name="proposed-changed-run-generator",
    type=WorkflowType.INTERNAL,
    module="infrahub.proposed_change.tasks",
    function="run_generators",
    tags=[WorkflowTag.DATABASE_CHANGE],
)

REQUEST_PROPOSED_CHANGE_REPOSITORY_CHECKS = WorkflowDefinition(
    name="proposed-changed-repository-checks",
    type=WorkflowType.INTERNAL,
    module="infrahub.proposed_change.tasks",
    function="repository_checks",
)

WEBHOOK_CONFIGURE = WorkflowDefinition(
    name="webhook-setup-automations",
    type=WorkflowType.USER,
    module="infrahub.webhook.tasks",
    function="configure_webhooks",
)

WEBHOOK_TRIGGER = WorkflowDefinition(
    name="webhook-trigger-actions",
    type=WorkflowType.USER,
    module="infrahub.webhook.tasks",
    function="trigger_webhooks",
)

AUTOMATION_SETUP_WEBHOOK_CONFIGURATION_TRIGGER = WorkflowDefinition(
    name="webhook-setup-configuration-trigger",
    type=WorkflowType.USER,
    module="infrahub.webhook.tasks",
    function="trigger_webhook_configuration",
)


worker_pools = [INFRAHUB_WORKER_POOL]

workflows = [
    ANONYMOUS_TELEMETRY_SEND,
    AUTOMATION_BRANCH_ACTIONS,
    AUTOMATION_GIT_UPDATED,
    AUTOMATION_SCHEMA_UPDATED,
    AUTOMATION_SETUP_WEBHOOK_CONFIGURATION_TRIGGER,
    BRANCH_CANCEL_PROPOSED_CHANGES,
    BRANCH_CREATE,
    BRANCH_DELETE,
    BRANCH_MERGE,
    BRANCH_MERGE_MUTATION,
    BRANCH_REBASE,
    BRANCH_VALIDATE,
    COMPUTED_ATTRIBUTE_REMOVE_PYTHON,
    COMPUTED_ATTRIBUTE_SETUP,
    COMPUTED_ATTRIBUTE_SETUP_PYTHON,
    DIFF_REFRESH,
    DIFF_REFRESH_ALL,
    DIFF_UPDATE,
    GIT_REPOSITORIES_CREATE_BRANCH,
    GIT_REPOSITORIES_DIFF_NAMES_ONLY,
    GIT_REPOSITORIES_IMPORT_OBJECTS,
    GIT_REPOSITORIES_MERGE,
    GIT_REPOSITORIES_PULL_READ_ONLY,
    GIT_REPOSITORIES_SYNC,
    GIT_REPOSITORY_ADD,
    GIT_REPOSITORY_ADD_READ_ONLY,
    GRAPHQL_QUERY_GROUP_UPDATE,
    IPAM_RECONCILIATION,
    PROCESS_COMPUTED_MACRO,
    PROPOSED_CHANGE_MERGE,
    QUERY_COMPUTED_ATTRIBUTE_TRANSFORM_TARGETS,
    REQUEST_ARTIFACT_DEFINITION_GENERATE,
    REQUEST_ARTIFACT_GENERATE,
    REQUEST_GENERATOR_DEFINITION_RUN,
    REQUEST_GENERATOR_RUN,
    REQUEST_PROPOSED_CHANGE_DATA_INTEGRITY,
    REQUEST_PROPOSED_CHANGE_REPOSITORY_CHECKS,
    REQUEST_PROPOSED_CHANGE_RUN_GENERATORS,
    REQUEST_PROPOSED_CHANGE_SCHEMA_INTEGRITY,
    REQUEST_PROPOSED_CHANGE_USER_TESTS,
    SCHEMA_APPLY_MIGRATION,
    SCHEMA_VALIDATE_MIGRATION,
    TRANSFORM_JINJA2_RENDER,
    TRANSFORM_PYTHON_RENDER,
    TRIGGER_ARTIFACT_DEFINITION_GENERATE,
    TRIGGER_GENERATOR_DEFINITION_RUN,
    TRIGGER_UPDATE_JINJA_COMPUTED_ATTRIBUTES,
    TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES,
    UPDATE_COMPUTED_ATTRIBUTE_TRANSFORM,
    WEBHOOK_CONFIGURE,
    WEBHOOK_SEND,
    WEBHOOK_TRIGGER,
]

automation_setup_workflows = [
    AUTOMATION_BRANCH_ACTIONS,
    AUTOMATION_GIT_UPDATED,
    AUTOMATION_SCHEMA_UPDATED,
    AUTOMATION_SETUP_WEBHOOK_CONFIGURATION_TRIGGER,
]
