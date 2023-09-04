from typing import Dict, Type

from infrahub.message_bus import InfrahubBaseMessage

from .check_repository_mergeconflicts import CheckRepositoryMergeConflicts
from .request_artifactdefinition_generate import RequestArtifactDefinitionGenerate
from .request_proposedchange_dataintegrity import RequestProposedChangeDataIntegrity
from .request_proposedchange_refreshartifacts import (
    RequestProposedChangeRefreshArtifacts,
)
from .request_proposedchange_repositorychecks import (
    RequestProposedChangeRepositoryChecks,
)
from .request_proposedchange_schemaintegrity import RequestProposedChangeSchemaIntegrity
from .request_repository_checks import RequestRepositoryChecks

MESSAGE_MAP: Dict[str, Type[InfrahubBaseMessage]] = {
    "check.repository.merge_conflicts": CheckRepositoryMergeConflicts,
    "request.artifact_definition.generate": RequestArtifactDefinitionGenerate,
    "request.proposed_change.data_integrity": RequestProposedChangeDataIntegrity,
    "request.proposed_change.refresh_artifacts": RequestProposedChangeRefreshArtifacts,
    "request.proposed_change.repository_checks": RequestProposedChangeRepositoryChecks,
    "request.proposed_change.schema_integrity": RequestProposedChangeSchemaIntegrity,
    "request.repository.checks": RequestRepositoryChecks,
}


ROUTING_KEY_MAP: Dict[Type[InfrahubBaseMessage], str] = {
    message: routing_key for routing_key, message in MESSAGE_MAP.items()
}
