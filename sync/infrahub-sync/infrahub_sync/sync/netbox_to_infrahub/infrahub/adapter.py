from infrahub_sync.adapters.infrahub import InfrahubAdapter

from .models import Location, Rack, Role, Tag


class InfrahubSync(InfrahubAdapter):
    tag = Tag
    role = Role
    rack = Rack
    location = Location
