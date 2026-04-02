import hashlib
import json
from typing import Any

from infrahub.database import InfrahubDatabase
from infrahub.telemetry.constants import (
    REMOTE_SEND_STATUS_FAILED,
    REMOTE_SEND_STATUS_PENDING,
    REMOTE_SEND_STATUS_SENT,
    REMOTE_SEND_STATUS_SKIPPED,
)
from infrahub.telemetry.snapshot import TelemetrySnapshot


def _sample_data(version: str = "1.2.3") -> dict:
    return {"deployment_id": "dep-123", "infrahub_version": version, "metric": 42}


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


async def test_create_snapshot(db: InfrahubDatabase, empty_database: None) -> None:
    snapshot = _make_snapshot()
    await snapshot.save(db=db)

    assert snapshot.id is not None
    assert snapshot.uuid is not None


async def test_get_by_uuid(db: InfrahubDatabase, empty_database: None) -> None:
    snapshot = _make_snapshot()
    await snapshot.save(db=db)

    retrieved = await TelemetrySnapshot.get(id=str(snapshot.uuid), db=db)
    assert retrieved is not None
    assert str(retrieved.uuid) == str(snapshot.uuid)
    assert retrieved.kind == "community"
    assert retrieved.deployment_id == "dep-123"
    assert retrieved.data == _sample_data()
    assert retrieved.checksum == snapshot.checksum
    assert retrieved.remote_send_status == REMOTE_SEND_STATUS_PENDING


async def test_get_list(db: InfrahubDatabase, empty_database: None) -> None:
    for i in range(3):
        data = _sample_data(version=f"1.0.{i}")
        s = _make_snapshot(data=data, checksum=_compute_checksum(data), infrahub_version=f"1.0.{i}")
        await s.save(db=db)

    snapshots = await TelemetrySnapshot.get_list(db=db)
    assert len(snapshots) == 3
    assert all(isinstance(s, TelemetrySnapshot) for s in snapshots)


async def test_update_remote_send_status(db: InfrahubDatabase, empty_database: None) -> None:
    snapshot = _make_snapshot()
    await snapshot.save(db=db)
    assert snapshot.remote_send_status == REMOTE_SEND_STATUS_PENDING

    snapshot.remote_send_status = REMOTE_SEND_STATUS_SENT
    await snapshot.save(db=db)

    retrieved = await TelemetrySnapshot.get(id=str(snapshot.uuid), db=db)
    assert retrieved is not None
    assert retrieved.remote_send_status == REMOTE_SEND_STATUS_SENT


async def test_update_to_skipped(db: InfrahubDatabase, empty_database: None) -> None:
    snapshot = _make_snapshot()
    await snapshot.save(db=db)

    snapshot.remote_send_status = REMOTE_SEND_STATUS_SKIPPED
    await snapshot.save(db=db)

    retrieved = await TelemetrySnapshot.get(id=str(snapshot.uuid), db=db)
    assert retrieved is not None
    assert retrieved.remote_send_status == REMOTE_SEND_STATUS_SKIPPED


async def test_update_to_failed(db: InfrahubDatabase, empty_database: None) -> None:
    snapshot = _make_snapshot()
    await snapshot.save(db=db)

    snapshot.remote_send_status = REMOTE_SEND_STATUS_FAILED
    await snapshot.save(db=db)

    retrieved = await TelemetrySnapshot.get(id=str(snapshot.uuid), db=db)
    assert retrieved is not None
    assert retrieved.remote_send_status == REMOTE_SEND_STATUS_FAILED
