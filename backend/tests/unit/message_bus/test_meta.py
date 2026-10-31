from __future__ import annotations

from infrahub.log import clear_log_context, get_log_data, set_log_data
from infrahub.message_bus import InfrahubMessage, Meta
from infrahub.services.adapters.message_bus.rabbitmq import _add_request_id


def test_assign_meta_propagates_user_request_id() -> None:
    parent = InfrahubMessage(meta=Meta(request_id="generated", user_request_id="caller-123"))
    child = InfrahubMessage()

    child.assign_meta(parent=parent)

    assert child.meta.request_id == "generated"
    assert child.meta.user_request_id == "caller-123"


def test_set_log_data_binds_user_request_id() -> None:
    clear_log_context()
    message = InfrahubMessage(meta=Meta(request_id="generated", user_request_id="caller-123"))

    message.set_log_data(routing_key="dummy.routing.key")

    log_data = get_log_data()
    assert log_data["request_id"] == "generated"
    assert log_data["user_request_id"] == "caller-123"
    clear_log_context()


def test_set_log_data_skips_empty_user_request_id() -> None:
    clear_log_context()
    message = InfrahubMessage(meta=Meta(request_id="generated"))

    message.set_log_data(routing_key="dummy.routing.key")

    assert "user_request_id" not in get_log_data()
    clear_log_context()


async def test_add_request_id_enricher_copies_user_request_id() -> None:
    clear_log_context()
    set_log_data(key="request_id", value="generated")
    set_log_data(key="user_request_id", value="caller-123")
    message = InfrahubMessage()

    await _add_request_id(message=message)

    assert message.meta.request_id == "generated"
    assert message.meta.user_request_id == "caller-123"
    clear_log_context()
