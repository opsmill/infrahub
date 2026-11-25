from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from infrahub_sdk import InfrahubClient

SET_GLOBAL_PREFERENCES = """
mutation (
  $date_format: DateFormat
  $timezone: String
  $instance_label: String
  $instance_color: InstanceColor
) {
  InfrahubSetPreferences(
    scope: GLOBAL
    date_format: $date_format
    timezone: $timezone
    instance_label: $instance_label
    instance_color: $instance_color
  ) {
    ok
  }
}
"""
UNSET_GLOBAL_PREFERENCES = {"date_format": None, "timezone": None, "instance_label": None, "instance_color": None}


@pytest.fixture(autouse=True)
async def reset_global_preferences(infrahub_client: InfrahubClient) -> AsyncGenerator[None, None]:
    """Clear the global preferences after each test, because every account on the session instance shares them."""
    yield
    await infrahub_client.execute_graphql(query=SET_GLOBAL_PREFERENCES, variables=UNSET_GLOBAL_PREFERENCES)
