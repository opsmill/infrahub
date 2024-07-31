from .base_with_diff import BaseProposedChangeWithDiffMessage


class RequestProposedChangeRepositoryChecks(BaseProposedChangeWithDiffMessage):
    """Sent when a proposed change is created to trigger additional checks"""
