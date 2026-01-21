from unittest.mock import AsyncMock, MagicMock, patch

from infrahub.lock import LOCK_PREFIX
from infrahub.locks.tasks import _extract_worker_id_from_gcl, clean_up_deadlocks, clean_up_stale_gcls
from infrahub.services import InfrahubServices
from infrahub.services.component import InfrahubComponent, WorkerInfo
from tests.adapters.cache import MemoryCache


async def test_clean_up_deadlocks(default_branch) -> None:
    cache = MemoryCache()
    await cache.set(
        key="lock.repository.sample-infrahub", value="2025-09-18T12:07:24.654862Z::800b4a90-87cd-458f-8c68-b0b5ebb81046"
    )

    component = AsyncMock(InfrahubComponent)
    component.list_workers.return_value = [WorkerInfo(identity="800b4a90-87cd-458f-8c68-b0b5ebb81046")]

    service = await InfrahubServices.new(cache=cache, component=component)

    await clean_up_deadlocks(service=service)

    component.list_workers.assert_awaited_once()
    assert not (await cache.list_keys(filter_pattern=f"{LOCK_PREFIX}*"))


def test_extract_worker_id_from_gcl_matching() -> None:
    """Test that worker ID is extracted from matching GCL names."""
    worker_id = _extract_worker_id_from_gcl("computed-attr-batch:abc-123-def")
    assert worker_id == "abc-123-def"


def test_extract_worker_id_from_gcl_non_matching() -> None:
    """Test that None is returned for non-matching GCL names."""
    worker_id = _extract_worker_id_from_gcl("some-other-gcl")
    assert worker_id is None


async def test_clean_up_stale_gcls_removes_inactive_worker_gcls(default_branch) -> None:
    """Test that GCLs from inactive workers are deleted."""
    cache = MemoryCache()

    # Mock component to return one active worker
    active_worker_id = "active-worker-id"
    inactive_worker_id = "inactive-worker-id"

    component = AsyncMock(InfrahubComponent)
    active_worker = WorkerInfo(identity=active_worker_id)
    active_worker.active = True
    component.list_workers.return_value = [active_worker]

    service = await InfrahubServices.new(cache=cache, component=component)

    # Mock Prefect client with GCLs
    mock_prefect_client = AsyncMock()

    active_gcl = MagicMock()
    active_gcl.name = f"computed-attr-batch:{active_worker_id}"

    stale_gcl = MagicMock()
    stale_gcl.name = f"computed-attr-batch:{inactive_worker_id}"

    mock_prefect_client.read_global_concurrency_limits.return_value = [active_gcl, stale_gcl]

    with patch("infrahub.locks.tasks.get_prefect_client") as mock_get_client:
        mock_get_client.return_value.__aenter__.return_value = mock_prefect_client
        await clean_up_stale_gcls(service=service)

    # Should delete only the stale GCL
    mock_prefect_client.delete_global_concurrency_limit_by_name.assert_called_once_with(
        f"computed-attr-batch:{inactive_worker_id}"
    )


async def test_clean_up_stale_gcls_ignores_non_matching_gcls(default_branch) -> None:
    """Test that GCLs not matching the pattern are ignored."""
    cache = MemoryCache()

    component = AsyncMock(InfrahubComponent)
    component.list_workers.return_value = []

    service = await InfrahubServices.new(cache=cache, component=component)

    # Mock Prefect client with non-matching GCL
    mock_prefect_client = AsyncMock()

    other_gcl = MagicMock()
    other_gcl.name = "some-other-gcl"

    mock_prefect_client.read_global_concurrency_limits.return_value = [other_gcl]

    with patch("infrahub.locks.tasks.get_prefect_client") as mock_get_client:
        mock_get_client.return_value.__aenter__.return_value = mock_prefect_client
        await clean_up_stale_gcls(service=service)

    # Should not attempt to delete non-matching GCLs
    mock_prefect_client.delete_global_concurrency_limit_by_name.assert_not_called()


async def test_clean_up_stale_gcls_keeps_active_worker_gcls(default_branch) -> None:
    """Test that GCLs from active workers are not deleted."""
    cache = MemoryCache()

    active_worker_id = "active-worker-id"

    component = AsyncMock(InfrahubComponent)
    active_worker = WorkerInfo(identity=active_worker_id)
    active_worker.active = True
    component.list_workers.return_value = [active_worker]

    service = await InfrahubServices.new(cache=cache, component=component)

    # Mock Prefect client with active worker GCL only
    mock_prefect_client = AsyncMock()

    active_gcl = MagicMock()
    active_gcl.name = f"computed-attr-batch:{active_worker_id}"

    mock_prefect_client.read_global_concurrency_limits.return_value = [active_gcl]

    with patch("infrahub.locks.tasks.get_prefect_client") as mock_get_client:
        mock_get_client.return_value.__aenter__.return_value = mock_prefect_client
        await clean_up_stale_gcls(service=service)

    # Should not delete active worker's GCL
    mock_prefect_client.delete_global_concurrency_limit_by_name.assert_not_called()
