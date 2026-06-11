"""Locations slice: continents and their countries.

Faithful transcription of ``models/infrastructure_edge.py``:

* data table ``CONTINENT_COUNTRIES`` (lines 393-400) — including the script's
  quirk of filing Mexico and Brazil under South America,
* ``generate_continents_countries`` (lines 2188-2208): every continent and
  country is created up front (countries pointing at the not-yet-saved
  continent node), then the continent batch executes before the country batch.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from data.common import save_with_retry
from data.handles import LocationsHandle

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

BRANCH = "main"

# continent name -> country names (models/infrastructure_edge.py lines 393-400)
CONTINENT_COUNTRIES = {
    "North America": ["United States of America", "Canada"],
    "South America": ["Mexico", "Brazil"],
    "Africa": ["Morocco", "Senegal"],
    "Europe": ["France", "Spain", "Italy"],
    "Asia": ["Japan", "China"],
    "Oceania": ["Australia", "New Zealand"],
}


@pytest.fixture(scope="session")
async def data_locations(
    data_client: InfrahubClient,
    schema_base: None,
    infrahub_provisioned_externally: bool,
) -> LocationsHandle:
    """Continents and countries of the demo dataset."""
    if infrahub_provisioned_externally:
        return LocationsHandle.external()

    continent_batch = await data_client.create_batch()
    country_batch = await data_client.create_batch()

    continents = {}
    countries = {}
    for continent, continent_countries in CONTINENT_COUNTRIES.items():
        continent_obj = await data_client.create(branch=BRANCH, kind="LocationContinent", name=continent)
        continent_batch.add(task=save_with_retry, node=continent_obj, obj=continent_obj)
        continents[continent] = continent_obj

        for country in continent_countries:
            country_obj = await data_client.create(
                branch=BRANCH, kind="LocationCountry", name=country, parent=continent_obj
            )
            country_batch.add(task=save_with_retry, node=country_obj, obj=country_obj)
            countries[country] = country_obj

    async for _ in continent_batch.execute():
        pass
    async for _ in country_batch.execute():
        pass

    return LocationsHandle(
        continents={key: node.id for key, node in continents.items()},
        countries={key: node.id for key, node in countries.items()},
    )
