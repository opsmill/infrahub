from typing import Dict, Type

from infrahub.message_bus import InfrahubBaseMessage

from .request_proposedchange_dataintegrity import RequestProposedChangeDataIntegrity
from .request_proposedchange_repositorychecks import (
    RequestProposedChangeRepositoryChecks,
)
from .request_proposedchange_schemaintegrity import RequestProposedChangeSchemaIntegrity
from .request_repository_checks import RequestRepositoryChecks

MESSAGE_MAP: Dict[str, Type[InfrahubBaseMessage]] = {
    "request.proposed_change.data_integrity": RequestProposedChangeDataIntegrity,
    "request.proposed_change.repository_checks": RequestProposedChangeRepositoryChecks,
    "request.proposed_change.schema_integrity": RequestProposedChangeSchemaIntegrity,
    "request.repository.checks": RequestRepositoryChecks,
}


ROUTING_KEY_MAP: Dict[Type[InfrahubBaseMessage], str] = {
    message: routing_key for routing_key, message in MESSAGE_MAP.items()
}
