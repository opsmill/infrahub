from infrahub.message_bus import InfrahubMessage


class RefreshRegistryBranches(InfrahubMessage):
    """Sent to indicate that the registry should be refreshed and new branch data loaded."""
