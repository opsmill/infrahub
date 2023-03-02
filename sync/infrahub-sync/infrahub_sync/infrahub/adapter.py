"""DiffSync Adapter for Infrahub to manage regions."""

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

        locations = await self.client.all(kind="Location")
        for location in locations:
            if str(location.type.value).lower() == "site":
                site = self.site(
                    slug=location.name.value,
                    name=location.name.value,
                    internal_id=location.id,
                    description=location.description.value,
                )
                self.add(site)

            elif str(location.type.value).lower() == "region":
                region = self.region(
                    slug=location.name.value,
                    name=location.name.value,
                    internal_id=location.id,
                    description=location.description.value,
                )
                self.add(region)
