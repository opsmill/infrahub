from infrahub_sync.adapters.netbox import NetboxAdapter

from .models import Location, Rack, Role, Tag


class NetboxSync(NetboxAdapter):
    tag = Tag
    role = Role
    rack = Rack
    location = Location
