
from infrahub_sync.adapters.netbox import NetboxAdapter

from .models import (
   Role,
   Location,
   Tag,
   Rack,
)


class NetboxSync(NetboxAdapter):
  role = Role
  location = Location
  tag = Tag
  rack = Rack
