import pickle
import time
from datetime import datetime, timezone

import pytest
from aio_pika import DeliveryMode, Message

from infrahub.message_bus.events import DataMessageAction, MessageType
from infrahub.message_bus.rpc import InfrahubRpcClientTesting
from infrahub_client import UUIDT


@pytest.fixture
async def rpc_client():
    return InfrahubRpcClientTesting()


@pytest.fixture
def incoming_data_message_01():
    body = {
        "action": DataMessageAction.CREATE.value,
        "branch": "main",
        "node_id": str(UUIDT.new()),
        "node_kind": "device",
    }

    return Message(
        body=pickle.dumps(body),
        content_type="application/python-pickle",
        # content_encoding="text",
        delivery_mode=DeliveryMode.PERSISTENT,
        message_id=str(UUIDT.new()),
        timestamp=datetime.fromtimestamp(int(time.time()), tz=timezone.utc),
        type=MessageType.DATA.value,
    )
