from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

from infrahub.core.models import HashableModel
from infrahub.rack_elevation.models import RackRole  # noqa: TC001


class RackElevationRackMapping(HashableModel):
    """Marks a kind as a rack and names the attribute that holds its height in units."""

    role: Literal[RackRole.RACK]
    u_height: str = Field(description="Path to the Number attribute holding the rack height, `<attribute>__value`")


class RackElevationMountableTypeMapping(HashableModel):
    """Marks a kind as the type of a mounted item and names the attributes that hold its dimensions."""

    role: Literal[RackRole.MOUNTABLE_TYPE]
    u_height: str = Field(description="Path to the Number attribute holding the height in units")
    full_depth: str = Field(description="Path to the Boolean attribute that is true when the item uses both faces")
    weight: str | None = Field(default=None, description="Path to the Number attribute holding the weight")


class RackElevationMountableMapping(HashableModel):
    """Marks a kind as an item mounted in a rack and names the relationships and attributes that place it."""

    role: Literal[RackRole.MOUNTABLE]
    rack: str = Field(description="Name of the relationship to the rack, of cardinality one")
    position: str = Field(description="Path to the Number attribute holding the first unit the item uses")
    face: str = Field(description="Path to the Dropdown attribute holding the face, `front` or `rear`")
    type: str | None = Field(
        default=None,
        description="Name of the relationship to the item type, of cardinality one; required on a node, optional on a generic",
    )


type RackElevationSchema = Annotated[
    RackElevationRackMapping | RackElevationMountableTypeMapping | RackElevationMountableMapping,
    Field(discriminator="role"),
]
