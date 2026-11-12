"""Dataset, expected results and option protocol shared by every rack model.

An option supplies its schema and the code that creates the dataset with its own attribute names. Every kind must set
its display label to the `name` attribute, so the display label of an item, a type and a rack is its name.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

RACK_KIND = "LocationRack"
DEVICE_KIND = "DcimDevice"
ACCESSORY_KIND = "DcimRackAccessory"
DEVICE_TYPE_KIND = "DcimDeviceType"
ACCESSORY_TYPE_KIND = "DcimRackAccessoryType"

EXPECTED_KINDS = {
    RACK_KIND: "RACK",
    DEVICE_KIND: "MOUNTABLE",
    ACCESSORY_KIND: "MOUNTABLE",
    DEVICE_TYPE_KIND: "MOUNTABLE_TYPE",
    ACCESSORY_TYPE_KIND: "MOUNTABLE_TYPE",
}

ROLE_COLORS = {"leaf": "#4d90fe", "server": "#00d25b", "pdu": "#ff9800"}

RACK_HEIGHT = 12


@dataclass(frozen=True)
class RackSpec:
    name: str
    u_height: int


@dataclass(frozen=True)
class TypeSpec:
    name: str
    kind: str
    u_height: int
    full_depth: bool
    weight: int


@dataclass(frozen=True)
class ItemSpec:
    name: str
    kind: str
    role: str | None
    type_name: str | None
    rack_name: str
    position: int | None
    face: str | None


RACKS = [RackSpec(name="R1", u_height=RACK_HEIGHT), RackSpec(name="R2", u_height=RACK_HEIGHT)]

TYPES = [
    TypeSpec(name="Switch 1U", kind=DEVICE_TYPE_KIND, u_height=1, full_depth=True, weight=8),
    TypeSpec(name="Server 2U", kind=DEVICE_TYPE_KIND, u_height=2, full_depth=True, weight=25),
    TypeSpec(name="Vertical PDU", kind=DEVICE_TYPE_KIND, u_height=0, full_depth=False, weight=5),
    TypeSpec(name="Patch panel 1U", kind=ACCESSORY_TYPE_KIND, u_height=1, full_depth=False, weight=2),
    TypeSpec(name="Blanking panel 1U", kind=ACCESSORY_TYPE_KIND, u_height=1, full_depth=False, weight=1),
]

ITEMS = [
    ItemSpec("leaf1", DEVICE_KIND, "leaf", "Switch 1U", "R1", 12, "front"),
    ItemSpec("leaf2", DEVICE_KIND, "leaf", "Switch 1U", "R1", 11, "front"),
    ItemSpec("srv1", DEVICE_KIND, "server", "Server 2U", "R1", 1, "front"),
    ItemSpec("pp1", ACCESSORY_KIND, None, "Patch panel 1U", "R1", 10, "rear"),
    ItemSpec("blank1", ACCESSORY_KIND, None, "Blanking panel 1U", "R1", 10, "front"),
    ItemSpec("pdu1", DEVICE_KIND, "pdu", "Vertical PDU", "R1", None, None),
    ItemSpec("spare1", DEVICE_KIND, "leaf", "Switch 1U", "R1", None, None),
    ItemSpec("spare2", DEVICE_KIND, "leaf", None, "R2", None, None),
]


class RackOptionFixture(Protocol):
    """What a rack model supplies to run the shared contract tests."""

    async def load_schema(self, db: InfrahubDatabase, branch: Branch) -> None: ...

    async def create_dataset(self, db: InfrahubDatabase, branch: Branch) -> dict[str, str]:
        """Create the racks, types and items above; return the node ID of each rack, type and item by name."""
        ...

    def standard_update_mutation(
        self, item_name: str, item_id: str, rack_id: str, position: int | None, face: str | None
    ) -> tuple[str, dict[str, Any]]:
        """GraphQL document and variables that move the item with the model's own update mutation and attribute names.

        `face` is "front", "rear" or None.
        """
        ...


def _expected_item(
    ids: dict[str, str],
    name: str,
    *,
    placement: str,
    position: int | None,
    face: str | None,
    u_height: int,
    full_depth: bool,
    weight: int | None,
    type_name: str | None,
    role: str | None,
    kind: str,
) -> dict[str, Any]:
    return {
        "id": ids[name],
        "kind": kind,
        "display_label": name,
        "label": name,
        "color": ROLE_COLORS[role] if role else None,
        "type_id": ids[type_name] if type_name else None,
        "type_display_label": type_name,
        "placement": placement,
        "position": position,
        "face": face,
        "u_height": u_height,
        "full_depth": full_depth,
        "weight": weight,
    }


def expected_elevation(ids: dict[str, str], rack_name: str) -> dict[str, Any]:
    """The RackElevation result for the dataset with label_by "name" and color_by "role"."""
    if rack_name == "R2":
        return {
            "rack": {
                "id": ids["R2"],
                "kind": RACK_KIND,
                "display_label": "R2",
                "u_height": 12,
                "used_units": 0,
                "utilization": 0,
                "total_weight": None,
            },
            "items": [
                _expected_item(
                    ids,
                    "spare2",
                    placement="UNPOSITIONED",
                    position=None,
                    face=None,
                    u_height=0,
                    full_depth=False,
                    weight=None,
                    type_name=None,
                    role="leaf",
                    kind=DEVICE_KIND,
                )
            ],
        }
    return {
        "rack": {
            "id": ids["R1"],
            "kind": RACK_KIND,
            "display_label": "R1",
            "u_height": 12,
            "used_units": 5,
            "utilization": 41,
            "total_weight": 57,
        },
        "items": [
            _expected_item(
                ids,
                "leaf1",
                placement="MOUNTED",
                position=12,
                face="FRONT",
                u_height=1,
                full_depth=True,
                weight=8,
                type_name="Switch 1U",
                role="leaf",
                kind=DEVICE_KIND,
            ),
            _expected_item(
                ids,
                "leaf2",
                placement="MOUNTED",
                position=11,
                face="FRONT",
                u_height=1,
                full_depth=True,
                weight=8,
                type_name="Switch 1U",
                role="leaf",
                kind=DEVICE_KIND,
            ),
            _expected_item(
                ids,
                "blank1",
                placement="MOUNTED",
                position=10,
                face="FRONT",
                u_height=1,
                full_depth=False,
                weight=1,
                type_name="Blanking panel 1U",
                role=None,
                kind=ACCESSORY_KIND,
            ),
            _expected_item(
                ids,
                "pp1",
                placement="MOUNTED",
                position=10,
                face="REAR",
                u_height=1,
                full_depth=False,
                weight=2,
                type_name="Patch panel 1U",
                role=None,
                kind=ACCESSORY_KIND,
            ),
            _expected_item(
                ids,
                "srv1",
                placement="MOUNTED",
                position=1,
                face="FRONT",
                u_height=2,
                full_depth=True,
                weight=25,
                type_name="Server 2U",
                role="server",
                kind=DEVICE_KIND,
            ),
            _expected_item(
                ids,
                "spare1",
                placement="UNPOSITIONED",
                position=None,
                face=None,
                u_height=1,
                full_depth=True,
                weight=8,
                type_name="Switch 1U",
                role="leaf",
                kind=DEVICE_KIND,
            ),
            _expected_item(
                ids,
                "pdu1",
                placement="ZERO_U",
                position=None,
                face=None,
                u_height=0,
                full_depth=False,
                weight=5,
                type_name="Vertical PDU",
                role="pdu",
                kind=DEVICE_KIND,
            ),
        ],
    }


@dataclass(frozen=True)
class RefusedPlacement:
    item: str
    rack: str
    position: int | None
    face: str | None
    constraint: str
    through_standard_mutation: bool = True


REFUSED_PLACEMENTS = [
    RefusedPlacement("leaf2", "R1", 12, "front", "RACK_UNITS_OCCUPIED"),
    RefusedPlacement("leaf2", "R1", 12, "rear", "RACK_UNITS_OCCUPIED"),
    RefusedPlacement("srv1", "R1", 12, "front", "RACK_POSITION_OUT_OF_RANGE"),
    RefusedPlacement("srv1", "R1", 0, "front", "RACK_POSITION_OUT_OF_RANGE"),
    RefusedPlacement("pdu1", "R1", 5, "front", "RACK_ZERO_U_HAS_NO_POSITION"),
    RefusedPlacement("pp1", "R1", 10, "front", "RACK_UNITS_OCCUPIED"),
    RefusedPlacement("spare2", "R2", 1, "front", "RACK_TYPE_REQUIRED"),
    RefusedPlacement("leaf2", "R1", 5, None, "RACK_FACE_REQUIRED", through_standard_mutation=False),
    RefusedPlacement("leaf2", "leaf1", 5, "front", "RACK_NOT_A_RACK", through_standard_mutation=False),
    RefusedPlacement("R2", "R1", 5, "front", "RACK_NOT_MOUNTABLE", through_standard_mutation=False),
]


@dataclass(frozen=True)
class AcceptedPlacement:
    item: str
    rack: str
    position: int | None
    face: str | None


ACCEPTED_PLACEMENTS = [
    AcceptedPlacement("pp1", "R1", 3, "rear"),
    AcceptedPlacement("leaf2", "R2", 1, "front"),
    AcceptedPlacement("spare1", "R1", 5, "front"),
    AcceptedPlacement("leaf2", "R1", None, None),
]
