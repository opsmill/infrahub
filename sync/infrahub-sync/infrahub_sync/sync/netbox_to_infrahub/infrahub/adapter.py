
from infrahub_sync.adapters.infrahub import InfrahubAdapter

from .models import (
   Role,
   Location,
   Tag,
   Rack,
)


class InfrahubSync(InfrahubAdapter):
  role = Role
  location = Location
  tag = Tag
  rack = Rack
