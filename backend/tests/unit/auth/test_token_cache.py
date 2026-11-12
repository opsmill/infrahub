from infrahub.auth.token_cache import AccountTokenCache


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_token_resolves_to_its_account_until_the_ttl_elapses() -> None:
    clock = FakeClock()
    cache = AccountTokenCache(ttl_seconds=5, max_entries=10, clock=clock)

    cache.set_account_id(token="token-one", account_id="account-one")

    assert cache.enabled is True
    assert cache.get_account_id(token="token-one") == "account-one"
    clock.advance(4.9)
    assert cache.get_account_id(token="token-one") == "account-one"
    clock.advance(0.2)
    assert cache.get_account_id(token="token-one") is None


def test_unknown_token_misses() -> None:
    cache = AccountTokenCache(ttl_seconds=5, max_entries=10, clock=FakeClock())
    cache.set_account_id(token="token-one", account_id="account-one")

    assert cache.get_account_id(token="token-two") is None


def test_each_token_keeps_its_own_account() -> None:
    cache = AccountTokenCache(ttl_seconds=5, max_entries=10, clock=FakeClock())
    cache.set_account_id(token="token-one", account_id="account-one")
    cache.set_account_id(token="token-two", account_id="account-two")

    assert cache.get_account_id(token="token-one") == "account-one"
    assert cache.get_account_id(token="token-two") == "account-two"


def test_zero_ttl_disables_the_cache() -> None:
    cache = AccountTokenCache(ttl_seconds=0, max_entries=10, clock=FakeClock())
    cache.set_account_id(token="token-one", account_id="account-one")

    assert cache.enabled is False
    assert cache.get_account_id(token="token-one") is None


def test_oldest_entry_is_dropped_when_the_cache_is_full() -> None:
    cache = AccountTokenCache(ttl_seconds=5, max_entries=2, clock=FakeClock())
    cache.set_account_id(token="token-one", account_id="account-one")
    cache.set_account_id(token="token-two", account_id="account-two")
    cache.set_account_id(token="token-three", account_id="account-three")

    assert cache.get_account_id(token="token-one") is None
    assert cache.get_account_id(token="token-two") == "account-two"
    assert cache.get_account_id(token="token-three") == "account-three"


def test_clear_forgets_every_token() -> None:
    cache = AccountTokenCache(ttl_seconds=5, max_entries=10, clock=FakeClock())
    cache.set_account_id(token="token-one", account_id="account-one")

    cache.clear()

    assert cache.get_account_id(token="token-one") is None
