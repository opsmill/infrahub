"""Rack elevation slice: two racks, five item types and eight items.

Each rack model replaces the body of ``data_rack_elevation`` to load its own schema and create the dataset described in
``backend/tests/component/rack_elevation/dataset.py`` with its own attribute names.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from data.handles import RackElevationHandle


@pytest.fixture(scope="session")
async def data_rack_elevation(  # noqa: RUF029
    data_client: InfrahubClient,
    schema_base: None,
    infrahub_provisioned_externally: bool,
) -> RackElevationHandle:
    pytest.skip("No rack model on this branch")
