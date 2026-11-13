from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import pytest
from prefect.settings import temporary_settings

from infrahub.prefect_server.models import InfrahubEventfilterInput


@dataclass
class ReadWindowTestCase:
    name: str
    vacuum_enabled: set[str] | bool
    events_retention: timedelta
    retention_seconds: int | None
    expected: timedelta
    event_persister_enabled: bool = True


READ_WINDOW_TEST_CASES: list[ReadWindowTestCase] = [
    ReadWindowTestCase(
        name="event_persister_disabled_keeps_older_events",
        vacuum_enabled={"events", "flow_runs"},
        events_retention=timedelta(days=7),
        retention_seconds=None,
        expected=timedelta(days=180),
        event_persister_enabled=False,
    ),
    ReadWindowTestCase(
        name="event_persister_disabled_keeps_longer_retention",
        vacuum_enabled={"events", "flow_runs"},
        events_retention=timedelta(days=365),
        retention_seconds=None,
        expected=timedelta(days=365),
        event_persister_enabled=False,
    ),
    ReadWindowTestCase(
        name="request_sets_the_window_with_event_persister_disabled",
        vacuum_enabled={"events", "flow_runs"},
        events_retention=timedelta(days=7),
        retention_seconds=86400,
        expected=timedelta(days=1),
        event_persister_enabled=False,
    ),
    ReadWindowTestCase(
        name="events_deleted",
        vacuum_enabled={"events", "flow_runs"},
        events_retention=timedelta(days=7),
        retention_seconds=None,
        expected=timedelta(days=7),
    ),
    ReadWindowTestCase(
        name="false_switch_still_deletes_events",
        vacuum_enabled=False,
        events_retention=timedelta(days=7),
        retention_seconds=None,
        expected=timedelta(days=7),
    ),
    ReadWindowTestCase(
        name="events_kept_with_a_shorter_retention",
        vacuum_enabled={"flow_runs"},
        events_retention=timedelta(days=7),
        retention_seconds=None,
        expected=timedelta(days=180),
    ),
    ReadWindowTestCase(
        name="nothing_deleted",
        vacuum_enabled=set(),
        events_retention=timedelta(days=30),
        retention_seconds=None,
        expected=timedelta(days=180),
    ),
    ReadWindowTestCase(
        name="events_kept_with_a_longer_retention",
        vacuum_enabled={"flow_runs"},
        events_retention=timedelta(days=365),
        retention_seconds=None,
        expected=timedelta(days=365),
    ),
    ReadWindowTestCase(
        name="unknown_vacuum_type",
        vacuum_enabled={"evnts"},
        events_retention=timedelta(days=7),
        retention_seconds=None,
        expected=timedelta(days=180),
    ),
    ReadWindowTestCase(
        name="request_sets_the_window",
        vacuum_enabled={"flow_runs"},
        events_retention=timedelta(days=7),
        retention_seconds=86400,
        expected=timedelta(days=1),
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in READ_WINDOW_TEST_CASES])
def test_read_window_without_a_start(test_case: ReadWindowTestCase) -> None:
    """Without a retention in the request, the window is the event retention, or at least 180 days when events are kept."""
    with temporary_settings(
        updates={
            "server.services.db_vacuum.enabled": test_case.vacuum_enabled,
            "server.services.event_persister.enabled": test_case.event_persister_enabled,
            "server.events.retention_period": test_case.events_retention,
        }
    ):
        filter_input = InfrahubEventfilterInput(retention_seconds=test_case.retention_seconds)

        assert filter_input.retention == test_case.expected
