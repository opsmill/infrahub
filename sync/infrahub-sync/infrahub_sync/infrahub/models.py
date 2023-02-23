from infrahub_sync.models import Region, Site


class InfrahubRegion(Region):
    internal_id: str


class InfrahubSite(Site):
    internal_id: str
