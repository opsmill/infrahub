from typing import Optional

from infrahub_sync.models import Region, Site

from infrahub_client import InfrahubNode


class InfrahubRegion(Region):
    internal_id: Optional[str]

    @classmethod
    async def create(cls, diffsync, ids, attrs):
        schema = await diffsync.client.schema.get(kind="Location")

        data = {"name": ids["slug"], "description": attrs["description"], "type": "REGION"}
        node = InfrahubNode(client=diffsync.client, schema=schema, data=data)
        await node.save()

        return super().create(diffsync, ids=ids, attrs=attrs)

    # def update(self, attrs):

    #     return super().update(attrs)


class InfrahubSite(Site):
    internal_id: Optional[str]

    @classmethod
    async def create(cls, diffsync, ids, attrs):
        schema = await diffsync.client.schema.get(kind="Location")

        data = {"name": ids["slug"], "description": attrs["description"], "type": "SITE"}
        node = InfrahubNode(client=diffsync.client, schema=schema, data=data)
        await node.save()

        return super().create(diffsync, ids=ids, attrs=attrs)

    # def update(self, attrs):

    #     return super().update(attrs)
