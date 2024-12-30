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
from .git_file_get import GitFileGet, GitFileGetResponse
from .git_repository_connectivity import GitRepositoryConnectivity
from .proposed_change.request_proposedchange_refreshartifacts import RequestProposedChangeRefreshArtifacts
from .refresh_git_fetch import RefreshGitFetch
from .refresh_registry_branches import RefreshRegistryBranches
from .refresh_registry_rebasedbranch import RefreshRegistryRebasedBranch
from .request_artifactdefinition_check import RequestArtifactDefinitionCheck
from .request_generatordefinition_check import RequestGeneratorDefinitionCheck
from .request_proposedchange_pipeline import RequestProposedChangePipeline
from .request_repository_checks import RequestRepositoryChecks
from .request_repository_userchecks import RequestRepositoryUserChecks
from .send_echo_request import SendEchoRequest, SendEchoRequestResponse

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
    "git.file.get": GitFileGet,
    "git.repository.connectivity": GitRepositoryConnectivity,
    "refresh.git.fetch": RefreshGitFetch,
    "refresh.registry.branches": RefreshRegistryBranches,
    "refresh.registry.rebased_branch": RefreshRegistryRebasedBranch,
    "request.artifact_definition.check": RequestArtifactDefinitionCheck,
    "request.generator_definition.check": RequestGeneratorDefinitionCheck,
    "request.proposed_change.pipeline": RequestProposedChangePipeline,
    "request.proposed_change.refresh_artifacts": RequestProposedChangeRefreshArtifacts,
    "request.repository.checks": RequestRepositoryChecks,
    "request.repository.user_checks": RequestRepositoryUserChecks,
    "send.echo.request": SendEchoRequest,
}

RESPONSE_MAP: dict[str, type[InfrahubResponse]] = {
    "git.file.get": GitFileGetResponse,
    "send.echo.request": SendEchoRequestResponse,
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
    "transform.jinja.template": 4,
    "transform.python.data": 4,
}


def message_priority(routing_key: str) -> int:
    return PRIORITY_MAP.get(routing_key, 3)


ROUTING_KEY_MAP: dict[type[InfrahubMessage], str] = {
    message: routing_key for routing_key, message in MESSAGE_MAP.items()
}
