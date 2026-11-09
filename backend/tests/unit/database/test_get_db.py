from unittest.mock import patch

import pytest

from infrahub import config
from infrahub.database import get_db, validated_database


async def test_get_db_passes_configured_pool_settings_to_the_driver(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every pool setting an operator configures must reach the driver, not stop at the config layer."""
    monkeypatch.setattr(config.SETTINGS.database, "max_connection_pool_size", 7)
    monkeypatch.setattr(config.SETTINGS.database, "max_connection_lifetime", 240)
    monkeypatch.setattr(config.SETTINGS.database, "liveness_check_timeout", 15)
    # Mark the database as already validated so get_db does not open a real session.
    monkeypatch.setitem(validated_database, config.SETTINGS.database.database_name, True)

    with patch("infrahub.database.AsyncGraphDatabase") as graph_database:
        driver = await get_db()

    assert driver is graph_database.driver.return_value
    kwargs = graph_database.driver.call_args.kwargs
    assert kwargs["max_connection_pool_size"] == 7
    assert kwargs["max_connection_lifetime"] == 240
    assert kwargs["liveness_check_timeout"] == 15


async def test_get_db_leaves_unset_pool_timeouts_to_the_driver(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unset pool timeout must not be passed at all, so the driver's own default stays in charge."""
    monkeypatch.setattr(config.SETTINGS.database, "max_connection_lifetime", None)
    monkeypatch.setattr(config.SETTINGS.database, "liveness_check_timeout", None)
    monkeypatch.setitem(validated_database, config.SETTINGS.database.database_name, True)

    with patch("infrahub.database.AsyncGraphDatabase") as graph_database:
        await get_db()

    kwargs = graph_database.driver.call_args.kwargs
    assert "max_connection_lifetime" not in kwargs
    assert "liveness_check_timeout" not in kwargs
