from infrahub.core.branch import Branch
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.registry import Registry


def _branch(name: str, description: str = "") -> Branch:
    return Branch(name=name, description=description, status=BranchStatus.OPEN, is_default=False, sync_with_git=False)


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
