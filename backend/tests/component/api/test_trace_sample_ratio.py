from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest
from fastapi import FastAPI

from infrahub import config
from infrahub import trace as infrahub_trace
from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.events import TraceSampleRatioUpdatedEvent
from infrahub.message_bus.messages import RefreshSettingsTraceSampleRatio
from infrahub.services import InfrahubServices
from infrahub.trace import SampleRatioState, create_tracer_provider, get_sample_ratio_state
from tests.adapters.event import FailingInfrahubEvent, MemoryInfrahubEvent

if TYPE_CHECKING:
    from collections.abc import Iterator

    from fastapi.testclient import TestClient

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from tests.adapters.message_bus import BusRecorder

URL = "/api/troubleshooting/trace-sample-ratio"
ROUTING_KEY = "refresh.settings.trace_sample_ratio"
DEFAULT_RATIO = 0.1
TRACING_OFF_MESSAGE = "Tracing is not enabled on this instance; set INFRAHUB_TRACE_ENABLE"
ENDPOINT_PATH = "/api/troubleshooting/trace-sample-ratio"
DEFAULT_STATE_BODY = {
    "enabled": True,
    "default_ratio": DEFAULT_RATIO,
    "temporary_ratio": None,
    "expires_at": None,
    "ratio_in_force": DEFAULT_RATIO,
}


@pytest.fixture
def started_client(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    recorder_bus: BusRecorder,
    default_branch: Branch,
    create_test_admin: Node,
) -> Iterator[TestClient]:
    """Start the application with tracing off, so the startup does not replace the global tracer provider."""
    monkeypatch.setattr(config.SETTINGS.trace, "enable", False)
    with client:
        yield client


@pytest.fixture
def tracing_on(started_client: TestClient) -> Iterator[None]:
    """Turn tracing on after the startup, with a process sampler whose default ratio is 0.1."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(config.SETTINGS.trace, "enable", True)
        patch.setattr(infrahub_trace, "_process_sampler", None)
        provider = create_tracer_provider(
            service="infrahub-test", version="1.0", exporter_type="console", sample_ratio=DEFAULT_RATIO
        )
        yield
        provider.shutdown()


@pytest.fixture
def events(started_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> MemoryInfrahubEvent:
    recorder = MemoryInfrahubEvent()
    monkeypatch.setattr(_service(started_client), "event", recorder)
    return recorder


def _service(client: TestClient) -> InfrahubServices:
    assert isinstance(client.app, FastAPI)
    service = client.app.state.service
    assert isinstance(service, InfrahubServices)
    return service


def _sent_messages(bus: BusRecorder) -> list[RefreshSettingsTraceSampleRatio]:
    messages = bus.messages_per_routing_key.get(ROUTING_KEY, [])
    return [message for message in messages if isinstance(message, RefreshSettingsTraceSampleRatio)]


async def test_get_returns_the_sampling_state(
    started_client: TestClient, admin_headers: dict[str, str], tracing_on: None
) -> None:
    response = started_client.get(URL, headers=admin_headers)

    assert response.status_code == 200
    assert response.json() == DEFAULT_STATE_BODY


async def test_get_reports_tracing_off(started_client: TestClient, admin_headers: dict[str, str]) -> None:
    response = started_client.get(URL, headers=admin_headers)

    assert response.status_code == 200
    assert response.json() == {
        "enabled": False,
        "default_ratio": None,
        "temporary_ratio": None,
        "expires_at": None,
        "ratio_in_force": None,
    }


async def test_put_requires_super_admin(
    db: InfrahubDatabase,
    started_client: TestClient,
    first_account: Node,
    recorder_bus: BusRecorder,
    events: MemoryInfrahubEvent,
    tracing_on: None,
) -> None:
    token = await Node.init(db=db, schema=InfrahubKind.ACCOUNTTOKEN)
    await token.new(db=db, token="unprivileged", account=first_account)
    await token.save(db=db)

    response = started_client.put(
        URL, headers={"X-INFRAHUB-KEY": "unprivileged"}, json={"ratio": 1.0, "duration_seconds": 1800}
    )

    assert response.status_code == 403
    assert (
        response.json()["errors"][0]["message"]
        == "You do not have the following permission: global:super_admin:allow_all"
    )
    assert _sent_messages(recorder_bus) == []
    assert events.events == []
    assert get_sample_ratio_state() == SampleRatioState(default_ratio=DEFAULT_RATIO, ratio_in_force=DEFAULT_RATIO)


@dataclass
class RefusedChangeCase:
    name: str
    method: str
    body: dict[str, Any] | None


REFUSED_CHANGE_CASES: list[RefusedChangeCase] = [
    RefusedChangeCase(name="put", method="PUT", body={"ratio": 1.0, "duration_seconds": 1800}),
    RefusedChangeCase(name="delete", method="DELETE", body=None),
]


@pytest.mark.parametrize("case", [pytest.param(tc, id=tc.name) for tc in REFUSED_CHANGE_CASES])
async def test_change_is_refused_when_tracing_is_off(
    started_client: TestClient,
    admin_headers: dict[str, str],
    recorder_bus: BusRecorder,
    events: MemoryInfrahubEvent,
    case: RefusedChangeCase,
) -> None:
    response = started_client.request(case.method, URL, headers=admin_headers, json=case.body)

    assert response.status_code == 400
    assert response.json() == {"data": None, "errors": [{"message": TRACING_OFF_MESSAGE, "extensions": {"code": 400}}]}
    assert _sent_messages(recorder_bus) == []
    assert events.events == []


@dataclass
class InvalidDurationCase:
    name: str
    duration_seconds: int


INVALID_DURATION_CASES: list[InvalidDurationCase] = [
    InvalidDurationCase(name="zero", duration_seconds=0),
    InvalidDurationCase(name="over_one_day", duration_seconds=86401),
]


@pytest.mark.parametrize("case", [pytest.param(tc, id=tc.name) for tc in INVALID_DURATION_CASES])
async def test_put_rejects_a_duration_outside_one_second_to_one_day(
    started_client: TestClient,
    admin_headers: dict[str, str],
    recorder_bus: BusRecorder,
    events: MemoryInfrahubEvent,
    tracing_on: None,
    case: InvalidDurationCase,
) -> None:
    response = started_client.put(
        URL, headers=admin_headers, json={"ratio": 1.0, "duration_seconds": case.duration_seconds}
    )

    assert response.status_code == 422
    assert _sent_messages(recorder_bus) == []
    assert events.events == []
    assert get_sample_ratio_state() == SampleRatioState(default_ratio=DEFAULT_RATIO, ratio_in_force=DEFAULT_RATIO)


async def test_put_sets_the_temporary_ratio_then_delete_clears_it(
    started_client: TestClient,
    admin_headers: dict[str, str],
    create_test_admin: Node,
    recorder_bus: BusRecorder,
    events: MemoryInfrahubEvent,
    tracing_on: None,
) -> None:
    before = datetime.now(tz=UTC)
    put_response = started_client.put(URL, headers=admin_headers, json={"ratio": 1.0, "duration_seconds": 1800})
    after = datetime.now(tz=UTC)

    assert put_response.status_code == 200
    put_body = put_response.json()
    expires_at = datetime.fromisoformat(put_body.pop("expires_at"))
    assert before + timedelta(seconds=1800) <= expires_at <= after + timedelta(seconds=1800)
    assert put_body == {"enabled": True, "default_ratio": DEFAULT_RATIO, "temporary_ratio": 1.0, "ratio_in_force": 1.0}

    (set_message,) = _sent_messages(recorder_bus)
    assert (set_message.ratio, set_message.expires_at) == (1.0, expires_at)

    (set_event,) = events.events
    assert isinstance(set_event, TraceSampleRatioUpdatedEvent)
    assert set_event.meta.account_id == create_test_admin.id
    assert (set_event.previous_ratio, set_event.new_ratio, set_event.expires_at, set_event.cleared) == (
        DEFAULT_RATIO,
        1.0,
        expires_at,
        False,
    )

    delete_response = started_client.delete(URL, headers=admin_headers)

    assert delete_response.status_code == 200
    assert delete_response.json() == DEFAULT_STATE_BODY

    clear_message = _sent_messages(recorder_bus)[1]
    assert (clear_message.ratio, clear_message.expires_at) == (None, None)

    clear_event = events.events[1]
    assert isinstance(clear_event, TraceSampleRatioUpdatedEvent)
    assert (clear_event.previous_ratio, clear_event.new_ratio, clear_event.expires_at, clear_event.cleared) == (
        1.0,
        DEFAULT_RATIO,
        None,
        True,
    )
    assert len(recorder_bus.messages_per_routing_key[ROUTING_KEY]) == 2
    assert len(events.events) == 2


async def test_put_succeeds_when_the_event_cannot_be_sent(
    started_client: TestClient,
    admin_headers: dict[str, str],
    recorder_bus: BusRecorder,
    monkeypatch: pytest.MonkeyPatch,
    tracing_on: None,
) -> None:
    monkeypatch.setattr(
        _service(started_client), "event", FailingInfrahubEvent(failing_kind=TraceSampleRatioUpdatedEvent)
    )

    response = started_client.put(URL, headers=admin_headers, json={"ratio": 1.0, "duration_seconds": 1800})

    assert response.status_code == 200
    assert response.json()["ratio_in_force"] == 1.0
    assert len(_sent_messages(recorder_bus)) == 1


async def test_new_change_replaces_the_active_one(
    started_client: TestClient,
    admin_headers: dict[str, str],
    recorder_bus: BusRecorder,
    events: MemoryInfrahubEvent,
    tracing_on: None,
) -> None:
    started_client.put(URL, headers=admin_headers, json={"ratio": 1.0, "duration_seconds": 1800})

    response = started_client.put(URL, headers=admin_headers, json={"ratio": 0.5, "duration_seconds": 60})

    assert response.status_code == 200
    body = response.json()
    expires_at = datetime.fromisoformat(body.pop("expires_at"))
    assert body == {"enabled": True, "default_ratio": DEFAULT_RATIO, "temporary_ratio": 0.5, "ratio_in_force": 0.5}
    assert get_sample_ratio_state() == SampleRatioState(
        default_ratio=DEFAULT_RATIO, ratio_in_force=0.5, temporary_ratio=0.5, expires_at=expires_at
    )
    assert [(message.ratio, message.expires_at) for message in _sent_messages(recorder_bus)][1] == (0.5, expires_at)
    second_event = events.events[1]
    assert isinstance(second_event, TraceSampleRatioUpdatedEvent)
    assert (second_event.previous_ratio, second_event.new_ratio) == (1.0, 0.5)


async def test_endpoints_are_documented_in_the_openapi_schema(started_client: TestClient) -> None:
    response = started_client.get("/api/openapi.json")

    operations = response.json()["paths"][ENDPOINT_PATH]
    assert set(operations) == {"get", "put", "delete"}
    for operation in operations.values():
        assert operation["tags"] == ["troubleshooting"]
        assert operation["summary"]
        assert operation["description"]
