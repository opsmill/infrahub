from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import GLOBAL_BRANCH_NAME
from infrahub.event_export.service import EventExportService, EventExportServiceCommunity
from infrahub.events.branch_action import BranchCreatedEvent
from infrahub.events.models import EventBranchContext, EventContext, EventMeta
from infrahub.services import InfrahubServices
from infrahub.services.adapters.event import InfrahubEventService
from infrahub.workers.dependencies import (
    build_event_export_service,
    build_event_service,
    build_message_bus,
    clear_singletons,
    get_event_export_service,
)
from tests.adapters.message_bus import BusRecorder, FailingBus
from tests.helpers.dependency_override import override_dependency

if TYPE_CHECKING:
    from collections.abc import Generator

    from fast_depends import Provider

    from infrahub.components import ComponentType
    from infrahub.events import InfrahubEvent


class RecordingEventExport(EventExportService):
    def __init__(self) -> None:
        self.captured: list[InfrahubEvent] = []

    async def start(self, component_type: ComponentType) -> None:
        pass

    async def capture(self, event: InfrahubEvent) -> None:
        self.captured.append(event)

    async def shutdown(self) -> None:
        pass


class FailingEventExport(RecordingEventExport):
    async def capture(self, event: InfrahubEvent) -> None:
        raise RuntimeError("export store unreachable")


def _branch_created_event() -> BranchCreatedEvent:
    meta = EventMeta(context=EventContext(branch=EventBranchContext(name=GLOBAL_BRANCH_NAME), account_id="account-1"))
    return BranchCreatedEvent(meta=meta, branch_name="feature", branch_id="branch-1", sync_with_git=False)


@pytest.fixture
def isolated_singletons() -> Generator[None, None, None]:
    clear_singletons()
    yield
    clear_singletons()


async def test_send_captures_each_event_once() -> None:
    export = RecordingEventExport()
    service = InfrahubEventService(message_bus=BusRecorder(), event_export=export)
    first = _branch_created_event()
    second = _branch_created_event()

    await service.send(event=first)
    await service.send(event=second)

    assert export.captured == [first, second]


async def test_capture_runs_when_the_message_bus_send_fails() -> None:
    export = RecordingEventExport()
    service = InfrahubEventService(message_bus=FailingBus(), event_export=export)
    event = _branch_created_event()

    with pytest.raises(ConnectionError):
        await service.send(event=event)

    assert export.captured == [event]


async def test_failing_capture_does_not_break_send(caplog: pytest.LogCaptureFixture) -> None:
    bus = BusRecorder()
    service = InfrahubEventService(message_bus=bus, event_export=FailingEventExport())

    with caplog.at_level(logging.ERROR):
        await service.send(event=_branch_created_event())

    assert len(bus.messages) == 1
    assert "export store unreachable" in caplog.text


async def test_built_event_service_receives_the_export_service(
    dependency_provider: Provider, isolated_singletons: None
) -> None:
    export = RecordingEventExport()
    bus = BusRecorder()

    async def _bus() -> BusRecorder:
        return bus

    with (
        override_dependency(build_message_bus, _bus, dependency_provider=dependency_provider),
        override_dependency(build_event_export_service, lambda: export, dependency_provider=dependency_provider),
    ):
        event_service = await build_event_service()

    assert event_service.event_export is export


async def test_services_pass_the_export_service_to_the_event_service(
    dependency_provider: Provider, isolated_singletons: None
) -> None:
    export = RecordingEventExport()

    with override_dependency(build_event_export_service, lambda: export, dependency_provider=dependency_provider):
        services = await InfrahubServices.new(message_bus=BusRecorder())

    assert services.event.event_export is export
    assert services.event_export is export


def test_community_export_service_is_the_default(isolated_singletons: None) -> None:
    assert isinstance(get_event_export_service(), EventExportServiceCommunity)
