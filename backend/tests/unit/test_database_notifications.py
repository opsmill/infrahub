"""Tests for Neo4j driver notification configuration.

Verifies that the Neo4j driver is configured to suppress irrelevant warnings
such as 'relationship type does not exist' for optional relationship types
like HAS_OWNER and HAS_SOURCE.

See: https://github.com/opsmill/infrahub/issues/8620
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from neo4j import NotificationDisabledClassification

from infrahub.database import get_db


@pytest.fixture
def _mock_db_settings():
    """Mock database settings for testing get_db configuration."""
    settings_patch = patch("infrahub.database.config.SETTINGS")
    with settings_patch as mock_settings:
        mock_settings.database.database_uri = "bolt://localhost:7687"
        mock_settings.database.username = "neo4j"
        mock_settings.database.password = "test"
        mock_settings.database.tls_enabled = False
        mock_settings.database.tls_insecure = False
        mock_settings.database.tls_ca_file = None
        mock_settings.database.database_name = "neo4j"
        yield mock_settings


@pytest.fixture
def _mock_driver():
    """Mock AsyncGraphDatabase.driver to capture its configuration."""
    with patch("infrahub.database.AsyncGraphDatabase") as mock_graph_db:
        mock_driver = AsyncMock()
        mock_graph_db.driver.return_value = mock_driver
        yield mock_graph_db


@pytest.fixture
def _skip_validation():
    """Skip database validation during get_db."""
    with patch("infrahub.database.validated_database", {"neo4j"}):
        yield


@pytest.mark.asyncio
async def test_get_db_disables_schema_notification_classification(
    _mock_db_settings,
    _mock_driver,
    _skip_validation,
) -> None:
    """The driver must disable SCHEMA notifications to suppress warnings about
    non-existent relationship types like HAS_OWNER and HAS_SOURCE.

    When an Infrahub instance has never had owner/source metadata set,
    these relationship types don't exist in the database. Neo4j (especially
    in clustered mode) emits GQL status 01N51 warnings classified as SCHEMA
    for queries that reference these types via OPTIONAL MATCH.

    These warnings are noisy and irrelevant for optional metadata relationships.
    The driver configuration must include SCHEMA in the disabled classifications
    to prevent them from appearing in logs.
    """
    await get_db()

    from infrahub.database import AsyncGraphDatabase

    call_kwargs = AsyncGraphDatabase.driver.call_args
    disabled_classifications = call_kwargs.kwargs.get(
        "notifications_disabled_classifications",
        call_kwargs.kwargs.get("notifications_disabled_categories", []),
    )

    assert NotificationDisabledClassification.SCHEMA in disabled_classifications, (
        "SCHEMA classification must be disabled to suppress 'relationship type does not exist' "
        "warnings (GQL status 01N51) for optional relationship types like HAS_OWNER and HAS_SOURCE. "
        "See https://github.com/opsmill/infrahub/issues/8620"
    )


@pytest.mark.asyncio
async def test_get_db_disables_unrecognized_notification_classification(
    _mock_db_settings,
    _mock_driver,
    _skip_validation,
) -> None:
    """The driver must also disable UNRECOGNIZED notifications as a catch-all
    for unknown notification classifications from newer server versions."""
    await get_db()

    from infrahub.database import AsyncGraphDatabase

    call_kwargs = AsyncGraphDatabase.driver.call_args
    disabled_classifications = call_kwargs.kwargs.get(
        "notifications_disabled_classifications",
        call_kwargs.kwargs.get("notifications_disabled_categories", []),
    )

    assert NotificationDisabledClassification.UNRECOGNIZED in disabled_classifications, (
        "UNRECOGNIZED classification must be disabled as a catch-all for "
        "unknown notification classifications from newer Neo4j server versions."
    )


@pytest.mark.asyncio
async def test_get_db_notification_severity_set_to_warning(
    _mock_db_settings,
    _mock_driver,
    _skip_validation,
) -> None:
    """The driver must set minimum notification severity to WARNING to avoid
    lower-severity noise in logs."""
    from neo4j import NotificationMinimumSeverity

    await get_db()

    from infrahub.database import AsyncGraphDatabase

    call_kwargs = AsyncGraphDatabase.driver.call_args
    min_severity = call_kwargs.kwargs.get("notifications_min_severity")

    assert min_severity == NotificationMinimumSeverity.WARNING
