from infrahub.message_bus import InfrahubMessage, InfrahubResponse

from .check_generator_run import CheckGeneratorRun
from .event_branch_merge import EventBranchMerge
from .finalize_validator_execution import FinalizeValidatorExecution
from .git_file_get import GitFileGet, GitFileGetResponse
from .git_repository_connectivity import GitRepositoryConnectivity
from .proposed_change.request_proposedchange_refreshartifacts import RequestProposedChangeRefreshArtifacts
from .refresh_git_fetch import RefreshGitFetch
from .refresh_registry_branches import RefreshRegistryBranches
from .refresh_registry_rebasedbranch import RefreshRegistryRebasedBranch
from .request_generatordefinition_check import RequestGeneratorDefinitionCheck
from .request_proposedchange_pipeline import RequestProposedChangePipeline
from .send_echo_request import SendEchoRequest, SendEchoRequestResponse

MESSAGE_MAP: dict[str, type[InfrahubMessage]] = {
    "check.generator.run": CheckGeneratorRun,
    "event.branch.merge": EventBranchMerge,
    "finalize.validator.execution": FinalizeValidatorExecution,
    "git.file.get": GitFileGet,
    "git.repository.connectivity": GitRepositoryConnectivity,
    "refresh.git.fetch": RefreshGitFetch,
    "refresh.registry.branches": RefreshRegistryBranches,
    "refresh.registry.rebased_branch": RefreshRegistryRebasedBranch,
    "request.generator_definition.check": RequestGeneratorDefinitionCheck,
    "request.proposed_change.pipeline": RequestProposedChangePipeline,
    "request.proposed_change.refresh_artifacts": RequestProposedChangeRefreshArtifacts,
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
    "send.echo.request": 5,  # Currently only for testing purposes, will be removed once all message bus have been migrated to prefect
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
