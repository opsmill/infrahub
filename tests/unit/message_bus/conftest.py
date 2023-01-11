import pickle
import time
import uuid
from datetime import datetime

import pytest
from aio_pika import DeliveryMode, Message

from infrahub.message_bus.events import DataMessageAction, MessageType


@pytest.fixture
def incoming_data_message_01():

    body = {
        "action": DataMessageAction.CREATE.value,
        "branch": "main",
        "node_id": str(uuid.uuid4()),
        "node_kind": "device",
    }

    return Message(
        body=pickle.dumps(body),
        content_type="application/python-pickle",
        # content_encoding="text",
        delivery_mode=DeliveryMode.PERSISTENT,
        message_id=str(uuid.uuid4()),
        timestamp=datetime.utcfromtimestamp(int(time.time())),
        type=MessageType.DATA.value,
    )
