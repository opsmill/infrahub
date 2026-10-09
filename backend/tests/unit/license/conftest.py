from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.license import service

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture(autouse=True)
def unreported_license_failures() -> Generator[None, None, None]:
    """Start with no license service failure reported and put the record back, so log assertions hold in any order."""
    saved = set(service._reported_failure_types)
    service._reported_failure_types.clear()
    yield
    service._reported_failure_types.clear()
    service._reported_failure_types.update(saved)
