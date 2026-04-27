import pytest

from infrahub.core import registry


@pytest.fixture(autouse=True)
def set_registry_default_branch() -> None:
    registry._default_branch = "main"
