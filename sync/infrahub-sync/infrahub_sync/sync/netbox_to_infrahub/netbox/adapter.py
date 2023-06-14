from infrahub_sync.adapters.netbox import NetboxAdapter

from .models import Location, Rack, Role, Tag


class NetboxSync(NetboxAdapter):
    rack = Rack
    location = Location
    role = Role
    tag = Tag
