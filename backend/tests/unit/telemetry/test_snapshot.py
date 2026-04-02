import hashlib
import json
from typing import Any

import pytest
from pydantic import ValidationError

from infrahub.telemetry.constants import (
    REMOTE_SEND_STATUS_FAILED,
    REMOTE_SEND_STATUS_PENDING,
    REMOTE_SEND_STATUS_SENT,
    REMOTE_SEND_STATUS_SKIPPED,
)
from infrahub.telemetry.snapshot import TelemetrySnapshot


def _sample_data() -> dict:
    return {"deployment_id": "dep-123", "infrahub_version": "1.2.3", "some_metric": 42}


def _compute_checksum(data: dict) -> str:
    return hashlib.sha256(json.dumps(data).encode()).hexdigest()


def _make_snapshot(**overrides: Any) -> TelemetrySnapshot:
    data = overrides.pop("data", _sample_data())
    return TelemetrySnapshot(
        kind=overrides.pop("kind", "community"),
        payload_format=overrides.pop("payload_format", "20250318"),
        deployment_id=overrides.pop("deployment_id", "dep-123"),
        infrahub_version=overrides.pop("infrahub_version", "1.2.3"),
        data=data,
        checksum=overrides.pop("checksum", _compute_checksum(data)),
        remote_send_status=overrides.pop("remote_send_status", REMOTE_SEND_STATUS_PENDING),
    )


class TestTelemetrySnapshotModel:
    def test_create_valid_snapshot(self) -> None:
        snapshot = _make_snapshot()
        assert snapshot.kind == "community"
        assert snapshot.payload_format == "20250318"
        assert snapshot.deployment_id == "dep-123"
        assert snapshot.infrahub_version == "1.2.3"
        assert snapshot.data == _sample_data()
        assert snapshot.remote_send_status == REMOTE_SEND_STATUS_PENDING

    def test_checksum_computation(self) -> None:
        data = _sample_data()
        expected_checksum = hashlib.sha256(json.dumps(data).encode()).hexdigest()
        snapshot = _make_snapshot()
        assert snapshot.checksum == expected_checksum
        assert len(snapshot.checksum) == 64

    def test_default_remote_send_status_is_pending(self) -> None:
        data = _sample_data()
        snapshot = TelemetrySnapshot(
            kind="community",
            payload_format="20250318",
            deployment_id="dep-123",
            infrahub_version="1.2.3",
            data=data,
            checksum=_compute_checksum(data),
        )
        assert snapshot.remote_send_status == REMOTE_SEND_STATUS_PENDING

    def test_all_valid_remote_send_statuses(self) -> None:
        for status in (
            REMOTE_SEND_STATUS_PENDING,
            REMOTE_SEND_STATUS_SENT,
            REMOTE_SEND_STATUS_SKIPPED,
            REMOTE_SEND_STATUS_FAILED,
        ):
            snapshot = _make_snapshot(remote_send_status=status)
            assert snapshot.remote_send_status == status

    def test_invalid_remote_send_status_raises(self) -> None:
        with pytest.raises(ValidationError, match="remote_send_status"):
            _make_snapshot(remote_send_status="unknown")

    def test_empty_kind_raises(self) -> None:
        with pytest.raises(ValidationError, match="kind"):
            _make_snapshot(kind="")

    def test_whitespace_kind_raises(self) -> None:
        with pytest.raises(ValidationError, match="kind"):
            _make_snapshot(kind="   ")

    def test_empty_payload_format_raises(self) -> None:
        with pytest.raises(ValidationError, match="payload_format"):
            _make_snapshot(payload_format="")

    def test_invalid_checksum_too_short(self) -> None:
        with pytest.raises(ValidationError, match="checksum"):
            _make_snapshot(checksum="abc123")

    def test_invalid_checksum_uppercase(self) -> None:
        with pytest.raises(ValidationError, match="checksum"):
            _make_snapshot(checksum="A" * 64)

    def test_empty_data_raises(self) -> None:
        checksum = _compute_checksum({})
        with pytest.raises(ValidationError, match="data"):
            _make_snapshot(data={}, checksum=checksum)

    def test_serialization_to_db(self) -> None:
        snapshot = _make_snapshot()
        db_dict = snapshot.to_db()
        assert "uuid" in db_dict
        assert db_dict["kind"] == "community"
        assert db_dict["remote_send_status"] == REMOTE_SEND_STATUS_PENDING
        assert db_dict["deployment_id"] == "dep-123"

    def test_get_type(self) -> None:
        assert TelemetrySnapshot.get_type() == "TelemetrySnapshot"
