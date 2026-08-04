from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from infrahub import config
from infrahub.database import get_db

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def _set_max_connection_pool_size() -> Generator[None, None, None]:
    initial = config.SETTINGS.database.max_connection_pool_size
    config.SETTINGS.database.max_connection_pool_size = 17
    yield
    config.SETTINGS.database.max_connection_pool_size = initial


@pytest.mark.usefixtures("_set_max_connection_pool_size")
async def test_get_db_passes_max_connection_pool_size_to_driver() -> None:
    with (
        patch("infrahub.database.AsyncGraphDatabase.driver", return_value=MagicMock()) as driver_factory,
        patch("infrahub.database.validate_database", new=AsyncMock()),
    ):
        await get_db()

    assert driver_factory.call_args.kwargs["max_connection_pool_size"] == 17
