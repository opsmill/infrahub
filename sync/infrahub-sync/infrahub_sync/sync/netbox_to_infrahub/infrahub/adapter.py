
from infrahub_sync.adapters.infrahub import InfrahubAdapter

from .models import (
   Tag,
   Location,
   Role,
)


class InfrahubSync(InfrahubAdapter):
  tag = Tag
  location = Location
  role = Role
