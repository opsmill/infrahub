import pytest
from fast_depends import Depends, Provider, inject

from tests.helpers.dependency_override import override_dependency


class Real:
    pass


class Double:
    pass


def build() -> object:
    return Real()


@pytest.fixture
def provider() -> Provider:
    return Provider()


def resolved(provider: Provider) -> object:
    def lookup(value: object = Depends(build)) -> object:
        return value

    return inject(lookup, dependency_provider=provider)()


def test_override_is_removed_when_there_was_none_before(provider: Provider) -> None:
    assert isinstance(resolved(provider), Real)

    with override_dependency(build, lambda: Double(), dependency_provider=provider):  # noqa: PLW0108
        assert isinstance(resolved(provider), Double)

    assert build not in provider.overrides
    assert isinstance(resolved(provider), Real)


def test_nested_override_gives_the_outer_one_back(provider: Provider) -> None:
    outer = Double()
    inner = Double()

    with override_dependency(build, lambda: outer, dependency_provider=provider):
        with override_dependency(build, lambda: inner, dependency_provider=provider):
            assert resolved(provider) is inner

        assert resolved(provider) is outer

    assert build not in provider.overrides


def test_exception_inside_the_block_still_restores(provider: Provider) -> None:
    with (
        pytest.raises(RuntimeError, match=r"^boom$"),
        override_dependency(build, lambda: Double(), dependency_provider=provider),  # noqa: PLW0108
    ):
        raise RuntimeError("boom")

    assert build not in provider.overrides
    assert isinstance(resolved(provider), Real)
