from .base_with_diff import BaseProposedChangeWithDiffMessage


class RequestProposedChangeRunTests(BaseProposedChangeWithDiffMessage):
    """Sent trigger to run tests (smoke, units, integrations) for a proposed change."""
