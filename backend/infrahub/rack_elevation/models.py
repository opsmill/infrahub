from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from infrahub.rack_elevation.constants import ZERO_U_HEIGHT
from infrahub.utils import InfrahubStringEnum


class RackRole(InfrahubStringEnum):
    RACK = "rack"
    MOUNTABLE = "mountable"
    MOUNTABLE_TYPE = "mountable_type"


class RackFace(InfrahubStringEnum):
    FRONT = "front"
    REAR = "rear"


class RackItemPlacement(InfrahubStringEnum):
    MOUNTED = "mounted"
    UNPOSITIONED = "unpositioned"
    ZERO_U = "zero_u"


class RackElevationModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class RackElevationKindEntry(RackElevationModel):
    kind: str
    role: RackRole


class RackSnapshot(RackElevationModel):
    id: str
    kind: str
    display_label: str
    u_height: int


class RackItemSnapshot(RackElevationModel):
    id: str
    kind: str
    display_label: str
    type_id: str | None
    type_display_label: str | None
    position: int | None
    face: RackFace | None
    u_height: int
    full_depth: bool
    weight: int | None

    @property
    def placement(self) -> RackItemPlacement:
        if self.position is not None:
            return RackItemPlacement.MOUNTED
        if self.type_id is not None and self.u_height == ZERO_U_HEIGHT:
            return RackItemPlacement.ZERO_U
        return RackItemPlacement.UNPOSITIONED

    @property
    def is_zero_u(self) -> bool:
        return self.type_id is not None and self.u_height == ZERO_U_HEIGHT


class RackTotals(RackElevationModel):
    used_units: int
    utilization: int
    total_weight: int | None


class RackPlacementViolation(RackElevationModel):
    constraint: str
    field: str
    detail: str
