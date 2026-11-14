from infrahub.core.account import GlobalPermission, ObjectPermission
from infrahub.core.constants import GlobalPermissions, PermissionAction, PermissionDecision
from infrahub.permissions.cache import AccountPermissionCache
from infrahub.permissions.types import AssignedPermissions


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _editor_permissions() -> AssignedPermissions:
    return {
        "global_permissions": [
            GlobalPermission(
                action=GlobalPermissions.EDIT_DEFAULT_BRANCH.value, decision=PermissionDecision.ALLOW_ALL.value
            )
        ],
        "object_permissions": [
            ObjectPermission(
                namespace="*", name="*", action=PermissionAction.VIEW.value, decision=PermissionDecision.ALLOW_ALL.value
            )
        ],
    }


def test_permissions_are_served_until_the_ttl_elapses() -> None:
    clock = FakeClock()
    cache = AccountPermissionCache(ttl_seconds=5, max_entries=10, clock=clock)

    cache.set(account_id="account-one", branch_name="main", permissions=_editor_permissions())

    assert cache.enabled is True
    assert cache.get(account_id="account-one", branch_name="main") == _editor_permissions()
    clock.advance(4.9)
    assert cache.get(account_id="account-one", branch_name="main") == _editor_permissions()
    clock.advance(0.2)
    assert cache.get(account_id="account-one", branch_name="main") is None


def test_entries_are_keyed_by_account_and_branch() -> None:
    cache = AccountPermissionCache(ttl_seconds=5, max_entries=10, clock=FakeClock())
    empty: AssignedPermissions = {"global_permissions": [], "object_permissions": []}

    cache.set(account_id="account-one", branch_name="main", permissions=_editor_permissions())
    cache.set(account_id="account-one", branch_name="feature", permissions=empty)

    assert cache.get(account_id="account-one", branch_name="main") == _editor_permissions()
    assert cache.get(account_id="account-one", branch_name="feature") == empty
    assert cache.get(account_id="account-two", branch_name="main") is None


def test_a_caller_cannot_change_what_the_cache_serves() -> None:
    cache = AccountPermissionCache(ttl_seconds=5, max_entries=10, clock=FakeClock())
    stored = _editor_permissions()
    cache.set(account_id="account-one", branch_name="main", permissions=stored)
    stored["global_permissions"].clear()

    served = cache.get(account_id="account-one", branch_name="main")
    assert served == _editor_permissions()
    served["object_permissions"].clear()

    assert cache.get(account_id="account-one", branch_name="main") == _editor_permissions()


def test_zero_ttl_disables_the_cache() -> None:
    cache = AccountPermissionCache(ttl_seconds=0, max_entries=10, clock=FakeClock())
    cache.set(account_id="account-one", branch_name="main", permissions=_editor_permissions())

    assert cache.enabled is False
    assert cache.get(account_id="account-one", branch_name="main") is None


def test_oldest_entry_is_dropped_when_the_cache_is_full() -> None:
    cache = AccountPermissionCache(ttl_seconds=5, max_entries=2, clock=FakeClock())
    empty: AssignedPermissions = {"global_permissions": [], "object_permissions": []}
    cache.set(account_id="account-one", branch_name="main", permissions=empty)
    cache.set(account_id="account-two", branch_name="main", permissions=empty)
    cache.set(account_id="account-three", branch_name="main", permissions=empty)

    assert cache.get(account_id="account-one", branch_name="main") is None
    assert cache.get(account_id="account-two", branch_name="main") == empty
    assert cache.get(account_id="account-three", branch_name="main") == empty
