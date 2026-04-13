from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, create_autospec, patch

import pytest

from infrahub.telemetry.repository import TelemetrySnapshotRepository
from infrahub.telemetry.tasks import send_telemetry_push

if TYPE_CHECKING:
    from collections.abc import Iterator

LOGGER_NAME = "infrahub.telemetry.tasks"


def _build_telemetry_data_mock() -> MagicMock:
    data = MagicMock()
    data.model_dump.return_value = {"deployment_id": "dep-123", "infrahub_version": "1.0.0"}
    data.execution_time = 0.5
    return data


@pytest.fixture(autouse=True)
def _patch_prefect_logger() -> Iterator[None]:
    with patch(
        "infrahub.telemetry.tasks.get_run_logger",
        return_value=logging.getLogger(LOGGER_NAME),
    ):
        yield


@pytest.fixture
def telemetry_mocks() -> Iterator[dict[str, Any]]:
    """Combined fixture providing all mocks needed for telemetry workflow tests."""
    repo = create_autospec(TelemetrySnapshotRepository, spec_set=True, instance=True)
    repo.save.return_value = None
    with (
        patch(
            "infrahub.telemetry.tasks.gather_anonymous_telemetry_data",
            new_callable=AsyncMock,
            return_value=_build_telemetry_data_mock(),
        ) as mock_gather,
        patch("infrahub.telemetry.tasks.post_telemetry_data", new_callable=AsyncMock) as mock_post,
        patch("infrahub.telemetry.tasks.get_database", new_callable=AsyncMock, return_value=MagicMock()),
        patch("infrahub.telemetry.tasks.TelemetrySnapshotRepository", return_value=repo) as mock_repo_cls,
        patch("infrahub.telemetry.tasks.registry") as mock_registry,
    ):
        mock_registry.id = "dep-123"
        yield {
            "gather": mock_gather,
            "post": mock_post,
            "repo": repo,
            "repo_cls": mock_repo_cls,
            "registry": mock_registry,
        }


class TestSendTelemetryPushOptedOut:
    async def test_stores_locally_with_skipped_status(
        self,
        telemetry_mocks: dict[str, Any],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with (
            patch("infrahub.telemetry.tasks.config") as mock_config,
            caplog.at_level(logging.INFO, logger=LOGGER_NAME),
        ):
            mock_config.SETTINGS.main.telemetry_optout = True

            await send_telemetry_push.fn()

            telemetry_mocks["gather"].assert_awaited_once()
            # One save for the initial PENDING insert, one for the SKIPPED status update.
            assert telemetry_mocks["repo"].save.await_count == 2
            telemetry_mocks["post"].assert_not_awaited()
            assert "opted out" in caplog.text.lower()


class TestSendTelemetryPushOptedIn:
    async def test_stores_locally_and_sends_remote(
        self,
        telemetry_mocks: dict[str, Any],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with (
            patch("infrahub.telemetry.tasks.config") as mock_config,
            caplog.at_level(logging.INFO, logger=LOGGER_NAME),
        ):
            mock_config.SETTINGS.main.telemetry_optout = False
            mock_config.SETTINGS.main.telemetry_endpoint = "https://telemetry.example.com"

            await send_telemetry_push.fn()

            telemetry_mocks["gather"].assert_awaited_once()
            # One save for the initial PENDING insert, one for the SENT status update.
            assert telemetry_mocks["repo"].save.await_count == 2
            telemetry_mocks["post"].assert_awaited_once()
            assert "successfully" in caplog.text.lower()

    async def test_remote_failure_marks_as_failed(
        self,
        telemetry_mocks: dict[str, Any],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with (
            patch("infrahub.telemetry.tasks.config") as mock_config,
            caplog.at_level(logging.WARNING, logger=LOGGER_NAME),
        ):
            mock_config.SETTINGS.main.telemetry_optout = False
            mock_config.SETTINGS.main.telemetry_endpoint = "https://telemetry.example.com"
            telemetry_mocks["post"].side_effect = Exception("Network error")

            await send_telemetry_push.fn()

            telemetry_mocks["gather"].assert_awaited_once()
            assert telemetry_mocks["repo"].save.await_count == 2
            assert "failed to send" in caplog.text.lower()


class TestSendTelemetryPushLocalSaveFails:
    async def test_bails_out_when_initial_save_fails(
        self,
        telemetry_mocks: dict[str, Any],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """If the initial local save fails we must not continue and silently no-op the status update."""
        with (
            patch("infrahub.telemetry.tasks.config") as mock_config,
            caplog.at_level(logging.WARNING, logger=LOGGER_NAME),
        ):
            mock_config.SETTINGS.main.telemetry_optout = True
            telemetry_mocks["repo"].save.side_effect = Exception("DB unavailable")

            await send_telemetry_push.fn()

            # Only one save attempt (the failed initial one); no second attempt.
            assert telemetry_mocks["repo"].save.await_count == 1
            telemetry_mocks["post"].assert_not_awaited()
            assert "failed to store" in caplog.text.lower()
