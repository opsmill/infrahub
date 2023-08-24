from typing import Dict, Type

from infrahub.message_bus import InfrahubBaseMessage

from .request_proposedchange_repositorychecks import (
    RequestProposedChangeRepositoryChecks,
)
from .request_repository_checks import RequestRepositoryChecks

MESSAGE_MAP: Dict[str, Type[InfrahubBaseMessage]] = {
    "request.proposed_change.repository_checks": RequestProposedChangeRepositoryChecks,
    "request.repository.checks": RequestRepositoryChecks,
}


ROUTING_KEY_MAP: Dict[Type[InfrahubBaseMessage], str] = {
    message: routing_key for routing_key, message in MESSAGE_MAP.items()
}
