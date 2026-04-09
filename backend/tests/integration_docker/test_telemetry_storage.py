import asyncio
from urllib.parse import urlencode

from infrahub_sdk import InfrahubClient
from infrahub_sdk.testing.docker import TestInfrahubDockerClient

from infrahub.telemetry.constants import TELEMETRY_KIND, TELEMETRY_VERSION


class TestTelemetryStorage(TestInfrahubDockerClient):
    async def test_telemetry_snapshots_created_and_queryable(self, client: InfrahubClient) -> None:
        """Validate that the telemetry workflow runs on schedule, stores snapshots locally,
        and that they are queryable via the REST API."""

        snapshots = []
        max_retries = 180  # 3 minutes of polling at 1s intervals
        for _attempt in range(max_retries):
            params = urlencode({"limit": 10})
            url = f"{client.address}/api/telemetry/snapshots?{params}"
            response = await client._get(url=url, timeout=client.default_timeout)
            response.raise_for_status()
            data = response.json()
            snapshots = data.get("snapshots", [])
            if len(snapshots) >= 2:
                break
            await asyncio.sleep(1)

        assert len(snapshots) >= 2, (
            f"Expected at least 2 telemetry snapshots after {max_retries}s, got {len(snapshots)}"
        )
        assert data["count"] >= 2

        # Validate snapshot structure
        snapshot = snapshots[0]
        assert snapshot["id"]
        assert snapshot["created_at"]
        assert snapshot["kind"] == TELEMETRY_KIND
        assert snapshot["payload_format"] == TELEMETRY_VERSION
        assert snapshot["deployment_id"]
        assert snapshot["infrahub_version"]
        assert snapshot["remote_send_status"] == "skipped"

        # Validate checksum is a valid SHA-256 hex string
        checksum = snapshot["checksum"]
        assert len(checksum) == 64
        assert all(c in "0123456789abcdef" for c in checksum)

        # Validate telemetry data payload
        payload = snapshot["data"]
        assert isinstance(payload, dict)
        assert payload["infrahub_version"]
        assert payload["python_version"]
        assert payload["platform"]
        assert payload["schema_info"]["node_count"] > 0
        assert payload["database"]["database_type"]
        assert isinstance(payload["features"], dict)
        assert payload["branches"]["total"] >= 1
        assert isinstance(payload["workers"], dict)

        # Validate that the two snapshots have different checksums or timestamps
        assert snapshots[0]["created_at"] != snapshots[1]["created_at"]
