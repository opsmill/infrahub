from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

from infrahub.core.manager import NodeManager

if TYPE_CHECKING:
    from collections.abc import Iterable

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase
    from infrahub.rack_elevation.models import RackItemSnapshot


class ItemPresentation(BaseModel):
    label: str
    color: str | None


class RackItemPresenter:
    def __init__(self, db: InfrahubDatabase, branch: Branch, at: Timestamp | None) -> None:
        self.db = db
        self.branch = branch
        self.at = at

    async def present(
        self, items: Iterable[RackItemSnapshot], label_by: str | None, color_by: str | None
    ) -> dict[str, ItemPresentation]:
        items = list(items)
        attribute_names = [name for name in (label_by, color_by) if name]
        nodes: dict[str, Node] = {}
        if attribute_names:
            nodes = await NodeManager.get_many(
                db=self.db,
                ids=[item.id for item in items],
                fields=dict.fromkeys(attribute_names, True),
                branch=self.branch,
                at=self.at,
            )
        return {
            item.id: ItemPresentation(
                label=_read_label(node=nodes.get(item.id), label_by=label_by, default=item.display_label),
                color=_read_color(node=nodes.get(item.id), color_by=color_by),
            )
            for item in items
        }


def _read_label(node: Node | None, label_by: str | None, default: str) -> str:
    if node is None or not label_by:
        return default
    if node.get_schema().get_attribute_or_none(label_by) is None:
        return default
    value = getattr(node, label_by).value
    return default if value is None else str(value)


def _read_color(node: Node | None, color_by: str | None) -> str | None:
    if node is None or not color_by:
        return None
    attribute_schema = node.get_schema().get_attribute_or_none(color_by)
    if attribute_schema is None or attribute_schema.kind != "Dropdown":
        return None
    value = getattr(node, color_by).value
    for choice in attribute_schema.choices or []:
        if choice.name == value:
            return choice.color
    return None
