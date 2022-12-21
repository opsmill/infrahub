import pytest

from infrahub.message_bus.events import InfrahubMessage, InfrahubDataMessage


from aio_pika import DeliveryMode, Message


def test_message_init(incoming_data_message_01):

    message = InfrahubMessage.init(incoming_data_message_01)

    assert isinstance(message, InfrahubDataMessage)
