from infrahub.message_bus.events import InfrahubMessage, InfrahubDataMessage


def test_message_init(incoming_data_message_01):

    message = InfrahubMessage.convert(incoming_data_message_01)

    assert isinstance(message, InfrahubDataMessage)
