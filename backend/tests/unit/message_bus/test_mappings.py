from infrahub.message_bus.messages import MESSAGE_MAP
from infrahub.message_bus.operations import COMMAND_MAP


def test_message_command_overlap():
    """Verify that a command is defined for each message."""
    messages = sorted(list(MESSAGE_MAP.keys()))
    commands = sorted(list(COMMAND_MAP.keys()))
    assert messages == commands
