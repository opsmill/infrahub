"""DiffSync Adapter for Infrahub to manage regions."""


from diffsync import DiffSync
from infrahub_sync.netbox.client import NetboxClient
from infrahub_sync.netbox.models import NetboxRegion, NetboxSite

QUERY_GET_REGIONS = """
query {
    region_list {
        id
        name
        slug
        description
        parent {
            id
        }
        tags {
            id
        }
    }
}
"""

QUERY_GET_SITES = """
query {
    site_list {
        id
        name
        physical_address
        status
        slug
        description
        region {
            id
        }
    }
}
"""


class NetboxAdapter(DiffSync):
    region = NetboxRegion
    site = NetboxSite

    top_level = ["region", "site"]

    type = "NetBox"

    def __init__(self, *args, url: str, token: str, **kwargs):
        super().__init__(*args, **kwargs)

        if not url or not token:
            raise ValueError("Both url and token must be specified!")

        self.client = NetboxClient(address=url, token=token)

    async def load(self):
        """Load all data from Netbox into the internal cache after transformation."""

        await self.load_regions()
        await self.load_sites()

    async def load_sites(self):
        response = await self.client.execute_graphql(query=QUERY_GET_SITES)

        for item in response["site_list"]:
            site = self.site(
                slug=item["slug"],
                name=item["name"],
                internal_id=item["id"],
                description=item["description"],
            )
            self.add(site)

    async def load_regions(self):
        response = await self.client.execute_graphql(query=QUERY_GET_REGIONS)

        for item in response["region_list"]:
            region = self.region(
                slug=item["slug"],
                name=item["name"],
                internal_id=item["id"],
                description=item["description"],
            )
            self.add(region)
