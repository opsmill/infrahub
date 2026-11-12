from __future__ import annotations

from infrahub.rack_elevation.models import RackFace, RackItemSnapshot, RackSnapshot


def build_rack(u_height: int = 12, display_label: str = "R1") -> RackSnapshot:
    return RackSnapshot(id=f"rack-{display_label}", kind="LocationRack", display_label=display_label, u_height=u_height)


def build_item(  # noqa: PLR0913
    name: str,
    *,
    position: int | None = None,
    face: RackFace | None = None,
    u_height: int = 1,
    full_depth: bool = False,
    weight: int | None = None,
    typed: bool = True,
) -> RackItemSnapshot:
    return RackItemSnapshot(
        id=f"item-{name}",
        kind="DcimDevice",
        display_label=name,
        type_id=f"type-{name}" if typed else None,
        type_display_label=f"Type of {name}" if typed else None,
        position=position,
        face=face,
        u_height=u_height if typed else 0,
        full_depth=full_depth,
        weight=weight,
    )
