from infrahub.message_bus import InfrahubMessage


class RequestGitSync(InfrahubMessage):
    """Request remote repositories to be synced."""
