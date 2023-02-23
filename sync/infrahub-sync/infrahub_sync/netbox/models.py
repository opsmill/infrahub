from infrahub_sync.models import Region, Site


class NetboxRegion(Region):
    internal_id: str


class NetboxSite(Site):
    internal_id: str
