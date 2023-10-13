from infrahub.message_bus.events import InfrahubDataMessage, InfrahubMessage


def test_message_init(incoming_data_message_01):
    message = InfrahubMessage.convert(incoming_data_message_01)

    assert isinstance(message, InfrahubDataMessage)
