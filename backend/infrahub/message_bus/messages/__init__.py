from typing import Dict, Type

from infrahub.message_bus import InfrahubBaseMessage

from .check_repository_checkdefinition import CheckRepositoryCheckDefinition
from .check_repository_mergeconflicts import CheckRepositoryMergeConflicts
from .event_branch_create import EventBranchCreate
from .event_schema_update import EventSchemaUpdate
from .finalize_validator_execution import FinalizeValidatorExecution
from .git_branch_create import GitBranchCreate
from .git_file_get import GitFileGet
from .git_repository_add import GitRepositoryAdd
from .refresh_registry_branches import RefreshRegistryBranches
from .request_artifactdefinition_generate import RequestArtifactDefinitionGenerate
from .request_git_createbranch import RequestGitCreateBranch
from .request_proposedchange_dataintegrity import RequestProposedChangeDataIntegrity
from .request_proposedchange_refreshartifacts import (
    RequestProposedChangeRefreshArtifacts,
)
from .request_proposedchange_repositorychecks import (
    RequestProposedChangeRepositoryChecks,
)
from .request_proposedchange_schemaintegrity import RequestProposedChangeSchemaIntegrity
from .request_repository_checks import RequestRepositoryChecks
from .transform_jinja_template import TransformJinjaTemplate
from .transform_python_data import TransformPythonData

MESSAGE_MAP: Dict[str, Type[InfrahubBaseMessage]] = {
    "check.repository.check_definition": CheckRepositoryCheckDefinition,
    "check.repository.merge_conflicts": CheckRepositoryMergeConflicts,
    "git.branch.create": GitBranchCreate,
    "git.file.get": GitFileGet,
    "git.repository.add": GitRepositoryAdd,
    "event.branch.create": EventBranchCreate,
    "event.schema.update": EventSchemaUpdate,
    "finalize.validator.execution": FinalizeValidatorExecution,
    "request.git.create_branch": RequestGitCreateBranch,
    "refresh.registry.branches": RefreshRegistryBranches,
    "request.artifact_definition.generate": RequestArtifactDefinitionGenerate,
    "request.proposed_change.data_integrity": RequestProposedChangeDataIntegrity,
    "request.proposed_change.refresh_artifacts": RequestProposedChangeRefreshArtifacts,
    "request.proposed_change.repository_checks": RequestProposedChangeRepositoryChecks,
    "request.proposed_change.schema_integrity": RequestProposedChangeSchemaIntegrity,
    "request.repository.checks": RequestRepositoryChecks,
    "transform.jinja.template": TransformJinjaTemplate,
    "transform.python.data": TransformPythonData,
}


ROUTING_KEY_MAP: Dict[Type[InfrahubBaseMessage], str] = {
    message: routing_key for routing_key, message in MESSAGE_MAP.items()
}
