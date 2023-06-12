
from infrahub_sync.adapters.netbox import NetboxAdapter

from .models import (
   Tag,
   Location,
   Role,
)


class NetboxSync(NetboxAdapter):
  tag = Tag
  location = Location
  role = Role
