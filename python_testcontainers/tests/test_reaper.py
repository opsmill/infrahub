from __future__ import annotations

import re
import socket
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub_testcontainers.reaper import ComposeProjectReaper

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

ACKNOWLEDGEMENT_TIMEOUT_SECONDS = 0.2


class SocketPairConnector:
    """Opens a socket pair per connection and plays Ryuk on the far end with a scripted reply."""

    def __init__(self, reply: bytes, *, end_after_reply: bool) -> None:
        self.reply = reply
        self.end_after_reply = end_after_reply
        self.client_sides: list[socket.socket] = []
        self.ryuk_sides: list[socket.socket] = []

    def __call__(self) -> socket.socket:
        client_side, ryuk_side = socket.socketpair()
        ryuk_side.sendall(self.reply)
        if self.end_after_reply:
            ryuk_side.shutdown(socket.SHUT_WR)
        self.client_sides.append(client_side)
        self.ryuk_sides.append(ryuk_side)
        return client_side

    def received(self, connection_index: int) -> bytes:
        ryuk_side = self.ryuk_sides[connection_index]
        ryuk_side.settimeout(ACKNOWLEDGEMENT_TIMEOUT_SECONDS)
        chunks = []
        try:
            while chunk := ryuk_side.recv(4096):
                chunks.append(chunk)
        except TimeoutError:
            # The client keeps its connection open, so reading ends once nothing more arrives.
            pass
        return b"".join(chunks)

    def close(self) -> None:
        for connection in [*self.client_sides, *self.ryuk_sides]:
            connection.close()


@pytest.fixture(name="connector_factory")
def fixture_connector_factory() -> Generator[Callable[..., SocketPairConnector], None, None]:
    connectors: list[SocketPairConnector] = []

    def _factory(reply: bytes, *, end_after_reply: bool = False) -> SocketPairConnector:
        connector = SocketPairConnector(reply=reply, end_after_reply=end_after_reply)
        connectors.append(connector)
        return connector

    yield _factory

    for connector in connectors:
        connector.close()


def test_register_sends_the_compose_project_label_filter(
    connector_factory: Callable[..., SocketPairConnector],
) -> None:
    connector = connector_factory(reply=b"ACK\n")
    reaper = ComposeProjectReaper(connect=connector, acknowledgement_timeout=ACKNOWLEDGEMENT_TIMEOUT_SECONDS)

    reaper.register(project_name="infrahub-test-1a2b3c4d")

    assert connector.received(connection_index=0) == b"label=com.docker.compose.project%3Dinfrahub-test-1a2b3c4d\n"


def test_register_keeps_one_connection_open_for_every_project(
    connector_factory: Callable[..., SocketPairConnector],
) -> None:
    connector = connector_factory(reply=b"ACK\nACK\n")
    reaper = ComposeProjectReaper(connect=connector, acknowledgement_timeout=ACKNOWLEDGEMENT_TIMEOUT_SECONDS)

    reaper.register(project_name="infrahub-test-first")
    reaper.register(project_name="infrahub-test-second")

    assert len(connector.client_sides) == 1
    assert connector.client_sides[0].fileno() != -1
    assert connector.received(connection_index=0) == (
        b"label=com.docker.compose.project%3Dinfrahub-test-first\n"
        b"label=com.docker.compose.project%3Dinfrahub-test-second\n"
    )


@dataclass
class RegistrationFailureTestCase:
    name: str
    reply: bytes
    end_after_reply: bool
    expected_exception: type[OSError]
    expected_message: str


REGISTRATION_FAILURE_TEST_CASES: list[RegistrationFailureTestCase] = [
    RegistrationFailureTestCase(
        name="no_reply_times_out",
        reply=b"",
        end_after_reply=False,
        expected_exception=TimeoutError,
        expected_message="timed out",
    ),
    RegistrationFailureTestCase(
        name="connection_closed_without_reply",
        reply=b"",
        end_after_reply=True,
        expected_exception=ConnectionError,
        expected_message="Ryuk closed the connection before acknowledging the cleanup filter",
    ),
    RegistrationFailureTestCase(
        name="connection_closed_mid_reply",
        reply=b"AC",
        end_after_reply=True,
        expected_exception=ConnectionError,
        expected_message="Ryuk closed the connection before acknowledging the cleanup filter",
    ),
    RegistrationFailureTestCase(
        name="reply_other_than_acknowledgement",
        reply=b"NOK\n",
        end_after_reply=False,
        expected_exception=ConnectionError,
        expected_message="Ryuk replied b'NOK\\n' instead of acknowledging the cleanup filter",
    ),
]


@pytest.mark.parametrize(
    "test_case",
    [pytest.param(tc, id=tc.name) for tc in REGISTRATION_FAILURE_TEST_CASES],
)
def test_register_raises_and_closes_the_connection_when_ryuk_does_not_acknowledge(
    test_case: RegistrationFailureTestCase,
    connector_factory: Callable[..., SocketPairConnector],
) -> None:
    connector = connector_factory(reply=test_case.reply, end_after_reply=test_case.end_after_reply)
    reaper = ComposeProjectReaper(connect=connector, acknowledgement_timeout=ACKNOWLEDGEMENT_TIMEOUT_SECONDS)

    with pytest.raises(test_case.expected_exception, match=re.escape(test_case.expected_message)):
        reaper.register(project_name="infrahub-test-1a2b3c4d")

    assert connector.client_sides[0].fileno() == -1


def test_register_opens_a_new_connection_after_a_failed_registration(
    connector_factory: Callable[..., SocketPairConnector],
) -> None:
    connector = connector_factory(reply=b"")
    reaper = ComposeProjectReaper(connect=connector, acknowledgement_timeout=ACKNOWLEDGEMENT_TIMEOUT_SECONDS)
    with pytest.raises(TimeoutError, match="timed out"):
        reaper.register(project_name="infrahub-test-first")

    connector.reply = b"ACK\n"
    reaper.register(project_name="infrahub-test-second")

    assert [client_side.fileno() == -1 for client_side in connector.client_sides] == [True, False]
    assert connector.received(connection_index=1) == b"label=com.docker.compose.project%3Dinfrahub-test-second\n"
