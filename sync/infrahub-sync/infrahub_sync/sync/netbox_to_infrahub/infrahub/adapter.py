from infrahub_sync.adapters.infrahub import InfrahubAdapter

from .models import Location, Rack, Role, Tag


class InfrahubSync(InfrahubAdapter):
    rack = Rack
    location = Location
    role = Role
    tag = Tag
