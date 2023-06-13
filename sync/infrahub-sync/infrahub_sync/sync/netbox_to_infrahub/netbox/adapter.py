from infrahub_sync.adapters.netbox import NetboxAdapter

from .models import (
    Rack,
    Location,
    Role,
    Tag,
)


class NetboxSync(NetboxAdapter):
    rack = Rack
    location = Location
    role = Role
    tag = Tag
