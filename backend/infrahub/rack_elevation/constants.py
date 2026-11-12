from __future__ import annotations

from infrahub.utils import InfrahubStringEnum

FIRST_UNIT = 1
ZERO_U_HEIGHT = 0
PERCENT = 100

RACK_ELEVATION_LOCK_NAMESPACE = "rack_elevation"

ATTRIBUTE_VALUE_PATH_SUFFIX = "__value"
RACK_ELEVATION_RACK_NODE_KEY = "RackElevationRackNode"


class RackConstraint(InfrahubStringEnum):
    POSITION_OUT_OF_RANGE = "RACK_POSITION_OUT_OF_RANGE"
    UNITS_OCCUPIED = "RACK_UNITS_OCCUPIED"
    FACE_REQUIRED = "RACK_FACE_REQUIRED"
    ZERO_U_HAS_NO_POSITION = "RACK_ZERO_U_HAS_NO_POSITION"
    TYPE_REQUIRED = "RACK_TYPE_REQUIRED"
    NOT_A_RACK = "RACK_NOT_A_RACK"
    NOT_MOUNTABLE = "RACK_NOT_MOUNTABLE"


class RackPlaceArgument(InfrahubStringEnum):
    """Names of the RackElevationPlace arguments, used as the field name of a refused placement."""

    ITEM = "item"
    RACK = "rack"
    POSITION = "position"
    FACE = "face"


class RackTotalAttribute(InfrahubStringEnum):
    """Names of the calculated attributes Infrahub adds to every rack kind."""

    USED_UNITS = "rack_used_units"
    UTILIZATION = "rack_utilization"
    TOTAL_WEIGHT = "rack_total_weight"


RACK_TOTAL_DESCRIPTIONS = {
    RackTotalAttribute.USED_UNITS.value: "Units of the rack used on at least one face",
    RackTotalAttribute.UTILIZATION.value: "Percentage of the rack units in use, rounded down",
    RackTotalAttribute.TOTAL_WEIGHT.value: "Total weight of the items in the rack",
}
