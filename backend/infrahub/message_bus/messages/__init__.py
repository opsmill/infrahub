from infrahub.message_bus import InfrahubMessage, InfrahubResponse

from .check_artifact_create import CheckArtifactCreate
from .check_generator_run import CheckGeneratorRun
from .check_repository_checkdefinition import CheckRepositoryCheckDefinition
from .check_repository_mergeconflicts import CheckRepositoryMergeConflicts
from .check_repository_usercheck import CheckRepositoryUserCheck
from .event_branch_create import EventBranchCreate
from .event_branch_delete import EventBranchDelete
from .event_branch_merge import EventBranchMerge
from .event_branch_rebased import EventBranchRebased
from .event_node_mutated import EventNodeMutated
from .event_schema_update import EventSchemaUpdate
from .event_worker_newprimaryapi import EventWorkerNewPrimaryAPI
from .finalize_validator_execution import FinalizeValidatorExecution
from .git_diff_namesonly import GitDiffNamesOnly, GitDiffNamesOnlyResponse
from .git_file_get import GitFileGet, GitFileGetResponse
from .git_repository_add import GitRepositoryAdd
from .git_repository_connectivity import GitRepositoryConnectivity
from .git_repository_importobjects import GitRepositoryImportObjects
from .git_repository_read_only_add import GitRepositoryAddReadOnly
from .proposed_change.request_proposedchange_dataintegrity import RequestProposedChangeDataIntegrity
from .proposed_change.request_proposedchange_refreshartifacts import RequestProposedChangeRefreshArtifacts
from .proposed_change.request_proposedchange_repositorychecks import RequestProposedChangeRepositoryChecks
from .proposed_change.request_proposedchange_rungenerators import RequestProposedChangeRunGenerators
from .proposed_change.request_proposedchange_runtests import RequestProposedChangeRunTests
from .proposed_change.request_proposedchange_schemaintegrity import RequestProposedChangeSchemaIntegrity
from .refresh_registry_branches import RefreshRegistryBranches
from .refresh_registry_rebasedbranch import RefreshRegistryRebasedBranch
from .refresh_webhook_configuration import RefreshWebhookConfiguration
from .request_artifactdefinition_check import RequestArtifactDefinitionCheck
from .request_generatordefinition_check import RequestGeneratorDefinitionCheck
from .request_proposedchange_pipeline import RequestProposedChangePipeline
from .request_repository_checks import RequestRepositoryChecks
from .request_repository_userchecks import RequestRepositoryUserChecks
from .schema_migration_path import SchemaMigrationPath, SchemaMigrationPathResponse
from .schema_validator_path import SchemaValidatorPath, SchemaValidatorPathResponse
from .send_echo_request import SendEchoRequest, SendEchoRequestResponse
from .trigger_webhook_actions import TriggerWebhookActions

MESSAGE_MAP: dict[str, type[InfrahubMessage]] = {
    "check.artifact.create": CheckArtifactCreate,
    "check.generator.run": CheckGeneratorRun,
    "check.repository.check_definition": CheckRepositoryCheckDefinition,
    "check.repository.merge_conflicts": CheckRepositoryMergeConflicts,
    "check.repository.user_check": CheckRepositoryUserCheck,
    "event.branch.create": EventBranchCreate,
    "event.branch.delete": EventBranchDelete,
    "event.branch.merge": EventBranchMerge,
    "event.branch.rebased": EventBranchRebased,
    "event.node.mutated": EventNodeMutated,
    "event.schema.update": EventSchemaUpdate,
    "event.worker.new_primary_api": EventWorkerNewPrimaryAPI,
    "finalize.validator.execution": FinalizeValidatorExecution,
    "git.diff.names_only": GitDiffNamesOnly,
    "git.file.get": GitFileGet,
    "git.repository.add": GitRepositoryAdd,
    "git.repository.connectivity": GitRepositoryConnectivity,
    "git.repository.add_read_only": GitRepositoryAddReadOnly,
    "git.repository.import_objects": GitRepositoryImportObjects,
    "schema.migration.path": SchemaMigrationPath,
    "schema.validator.path": SchemaValidatorPath,
    "refresh.registry.branches": RefreshRegistryBranches,
    "refresh.registry.rebased_branch": RefreshRegistryRebasedBranch,
    "refresh.webhook.configuration": RefreshWebhookConfiguration,
    "request.artifact_definition.check": RequestArtifactDefinitionCheck,
    "request.generator_definition.check": RequestGeneratorDefinitionCheck,
    "request.proposed_change.data_integrity": RequestProposedChangeDataIntegrity,
    "request.proposed_change.pipeline": RequestProposedChangePipeline,
    "request.proposed_change.refresh_artifacts": RequestProposedChangeRefreshArtifacts,
    "request.proposed_change.repository_checks": RequestProposedChangeRepositoryChecks,
    "request.proposed_change.run_generators": RequestProposedChangeRunGenerators,
    "request.proposed_change.schema_integrity": RequestProposedChangeSchemaIntegrity,
    "request.proposed_change.run_tests": RequestProposedChangeRunTests,
    "request.repository.checks": RequestRepositoryChecks,
    "request.repository.user_checks": RequestRepositoryUserChecks,
    "send.echo.request": SendEchoRequest,
    "trigger.webhook.actions": TriggerWebhookActions,
}

RESPONSE_MAP: dict[str, type[InfrahubResponse]] = {
    "git.diff.names_only": GitDiffNamesOnlyResponse,
    "git.file.get": GitFileGetResponse,
    "send.echo.request": SendEchoRequestResponse,
    "schema.migration.path": SchemaMigrationPathResponse,
    "schema.validator.path": SchemaValidatorPathResponse,
}

PRIORITY_MAP = {
    "check.artifact.create": 2,
    "check.repository.check_definition": 2,
    "check.repository.merge_conflicts": 2,
    "event.branch.create": 5,
    "event.branch.delete": 5,
    "event.branch.merge": 5,
    "event.schema.update": 5,
    "git.diff.names_only": 4,
    "git.file.get": 4,
    "request.artifact.generate": 2,
    "request.git.sync": 4,
    "request.proposed_change.pipeline": 5,
    "request.proposed_change.repository_checks": 5,
    "transform.jinja.template": 4,
    "transform.python.data": 4,
}


def message_priority(routing_key: str) -> int:
    return PRIORITY_MAP.get(routing_key, 3)


ROUTING_KEY_MAP: dict[type[InfrahubMessage], str] = {
    message: routing_key for routing_key, message in MESSAGE_MAP.items()
}
