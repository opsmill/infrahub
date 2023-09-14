from infrahub.message_bus import InfrahubBaseMessage


class RefreshRegistryBranches(InfrahubBaseMessage):
    """Sent to indicate that the registry should be refreshed and new branch data loaded."""
