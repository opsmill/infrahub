"""DiffSync Adapter for Infrahub to manage regions."""

import pynautobot  # pylint: disable=import-error
from diffsync import DiffSync
from infrahub_sync.infrahub.models import InfrahubRegion, InfrahubSite

from infrahub_client import InfrahubClient


class InfrahubAdapter(DiffSync):
    region = InfrahubRegion
    site = InfrahubSite

    top_level = ["region", "site"]

    type = "Infrahub"

    def __init__(self, *args, url, **kwargs):
        super().__init__(*args, **kwargs)

        if not url:
            raise ValueError("url must be specified!")

        self.client = InfrahubClient(address=url)

    async def load(self):
        """Load all data from Infrahub into the internal cache after transformation."""


