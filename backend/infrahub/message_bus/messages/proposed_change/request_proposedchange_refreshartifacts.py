from .base_with_diff import BaseProposedChangeWithDiffMessage


class RequestProposedChangeRefreshArtifacts(BaseProposedChangeWithDiffMessage):
    """Sent trigger the refresh of artifacts that are impacted by the proposed change."""
