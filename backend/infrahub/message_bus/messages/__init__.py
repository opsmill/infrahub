from typing import Dict, Type

from infrahub.message_bus import InfrahubMessage

from .check_artifact_create import CheckArtifactCreate
from .check_repository_checkdefinition import CheckRepositoryCheckDefinition
from .check_repository_mergeconflicts import CheckRepositoryMergeConflicts
from .event_branch_create import EventBranchCreate
from .event_branch_delete import EventBranchDelete
from .event_branch_merge import EventBranchMerge
from .event_node_mutated import EventNodeMutated
from .event_schema_update import EventSchemaUpdate
from .finalize_validator_execution import FinalizeValidatorExecution
from .git_branch_create import GitBranchCreate
from .git_diff_namesonly import GitDiffNamesOnly
from .git_file_get import GitFileGet
from .git_repository_add import GitRepositoryAdd
from .git_repository_merge import GitRepositoryMerge
from .refresh_registry_branches import RefreshRegistryBranches
from .request_artifact_generate import RequestArtifactGenerate
from .request_artifactdefinition_check import RequestArtifactDefinitionCheck
from .request_artifactdefinition_generate import RequestArtifactDefinitionGenerate
from .request_git_createbranch import RequestGitCreateBranch
from .request_git_sync import RequestGitSync
from .request_proposed_change_cancel import RequestProposedChangeCancel
from .request_proposedchange_dataintegrity import RequestProposedChangeDataIntegrity
from .request_proposedchange_refreshartifacts import RequestProposedChangeRefreshArtifacts
from .request_proposedchange_repositorychecks import RequestProposedChangeRepositoryChecks
from .request_proposedchange_schemaintegrity import RequestProposedChangeSchemaIntegrity
from .request_repository_checks import RequestRepositoryChecks
from .transform_jinja_template import TransformJinjaTemplate
from .transform_python_data import TransformPythonData
from .trigger_artifact_definition_generate import TriggerArtifactDefinitionGenerate
from .trigger_proposed_change_cancel import TriggerProposedChangeCancel

MESSAGE_MAP: Dict[str, Type[InfrahubMessage]] = {
    "check.artifact.create": CheckArtifactCreate,
    "check.repository.check_definition": CheckRepositoryCheckDefinition,
    "check.repository.merge_conflicts": CheckRepositoryMergeConflicts,
    "event.branch.create": EventBranchCreate,
    "event.branch.delete": EventBranchDelete,
    "event.branch.merge": EventBranchMerge,
    "event.node.mutated": EventNodeMutated,
    "event.schema.update": EventSchemaUpdate,
    "finalize.validator.execution": FinalizeValidatorExecution,
    "git.branch.create": GitBranchCreate,
    "git.diff.names_only": GitDiffNamesOnly,
    "git.file.get": GitFileGet,
    "git.repository.add": GitRepositoryAdd,
    "git.repository.merge": GitRepositoryMerge,
    "refresh.registry.branches": RefreshRegistryBranches,
    "request.artifact.generate": RequestArtifactGenerate,
    "request.artifact_definition.check": RequestArtifactDefinitionCheck,
    "request.artifact_definition.generate": RequestArtifactDefinitionGenerate,
    "request.git.create_branch": RequestGitCreateBranch,
    "request.git.sync": RequestGitSync,
    "request.proposed_change.cancel": RequestProposedChangeCancel,
    "request.proposed_change.data_integrity": RequestProposedChangeDataIntegrity,
    "request.proposed_change.refresh_artifacts": RequestProposedChangeRefreshArtifacts,
    "request.proposed_change.repository_checks": RequestProposedChangeRepositoryChecks,
    "request.proposed_change.schema_integrity": RequestProposedChangeSchemaIntegrity,
    "request.repository.checks": RequestRepositoryChecks,
    "transform.jinja.template": TransformJinjaTemplate,
    "transform.python.data": TransformPythonData,
    "trigger.artifact_definition.generate": TriggerArtifactDefinitionGenerate,
    "trigger.proposed_change.cancel": TriggerProposedChangeCancel,
}


def message_priority(routing_key: str) -> int:
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
        "transform.jinja.template": 4,
        "transform.python.data": 4,
    }

    return PRIORITY_MAP.get(routing_key, 3)


ROUTING_KEY_MAP: Dict[Type[InfrahubMessage], str] = {
    message: routing_key for routing_key, message in MESSAGE_MAP.items()
}
