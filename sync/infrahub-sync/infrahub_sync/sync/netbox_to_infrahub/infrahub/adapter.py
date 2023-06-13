
from infrahub_sync.adapters.infrahub import InfrahubAdapter

from .models import (
   Rack,
   Location,
   Role,
   Tag,
)


class InfrahubSync(InfrahubAdapter):
  rack = Rack
  location = Location
  role = Role
  tag = Tag
