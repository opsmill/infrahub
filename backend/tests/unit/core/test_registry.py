from asyncio import Event, create_task, gather, sleep, wait_for

from infrahub import lock
from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.registry import Registry


def _branch(name: str, description: str = "", status: BranchStatus = BranchStatus.OPEN) -> Branch:
    return Branch(name=name, description=description, status=status, is_default=False, sync_with_git=False)


def test_refresh_cached_branch_replaces_an_entry_the_worker_holds() -> None:
    registry = Registry()
    registry.branch["branch1"] = _branch("branch1")

    registry.refresh_cached_branch(_branch("branch1", description="updated"))

    assert registry.branch["branch1"].description == "updated"


def test_refresh_cached_branch_leaves_a_branch_the_worker_does_not_hold_uncached() -> None:
    """Inserting here would cache a branch without its schema, which refresh_branches never repairs."""
    registry = Registry()

    registry.refresh_cached_branch(_branch("branch1"))

    assert "branch1" not in registry.branch


async def test_publish_branch_lands_after_the_copy_a_registry_refresh_in_flight_applies() -> None:
    registry = Registry()
    refresh_holds_lock = Event()
    finish_refresh = Event()

    async def refresh() -> None:
        async with lock.registry.local_schema_lock():
            refresh_holds_lock.set()
            await finish_refresh.wait()
            registry.branch["branch1"] = _branch("branch1", status=BranchStatus.MERGING)

    refresh_task = create_task(refresh())
    await wait_for(refresh_holds_lock.wait(), timeout=10)
    publish_task = create_task(registry.publish_branch(_branch("branch1", status=BranchStatus.MERGED)))
    # Yields once so the publication runs as far as it can while the refresh still holds the lock.
    await sleep(0)
    finish_refresh.set()
    await wait_for(gather(refresh_task, publish_task), timeout=10)

    assert registry.branch["branch1"].status == BranchStatus.MERGED
