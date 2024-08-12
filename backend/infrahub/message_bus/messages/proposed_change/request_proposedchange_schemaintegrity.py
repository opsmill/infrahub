from .base_with_diff import BaseProposedChangeWithDiffMessage


class RequestProposedChangeSchemaIntegrity(BaseProposedChangeWithDiffMessage):
    """Sent trigger schema integrity checks for a proposed change"""
