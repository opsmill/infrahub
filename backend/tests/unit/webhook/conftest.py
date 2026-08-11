import os
from collections.abc import Generator

import pytest


@pytest.fixture
def cleared_environment() -> Generator[None, None, None]:
    """Run with no environment variables set, then restore them, so env-sourced headers fail to resolve."""
    saved = dict(os.environ)
    os.environ.clear()
    yield
    os.environ.clear()
    os.environ.update(saved)
