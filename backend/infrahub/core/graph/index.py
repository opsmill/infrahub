from __future__ import annotations

from typing import List

from infrahub.database.constants import IndexType
from infrahub.database.index import IndexItem

node_indexes: List[IndexItem] = [
    IndexItem(name="node", label="Node", properties=["uuid"], type=IndexType.RANGE),
    IndexItem(name="node", label="Node", properties=["kind"], type=IndexType.RANGE),
    IndexItem(name="attr", label="Attribute", properties=["name"], type=IndexType.RANGE),
    IndexItem(name="attr_value", label="AttributeValue", properties=["value"], type=IndexType.RANGE),
    IndexItem(name="rel_uuid", label="Relationship", properties=["uuid"], type=IndexType.RANGE),
    IndexItem(name="rel_identifier", label="Relationship", properties=["name"], type=IndexType.RANGE),
]

rel_indexes: List[IndexItem] = [
    IndexItem(
        name="attr_from",
        label="HAS_ATTRIBUTE",
        properties=["from"],
        type=IndexType.RANGE,
    ),
    IndexItem(
        name="attr_branch",
        label="HAS_ATTRIBUTE",
        properties=["branch"],
        type=IndexType.RANGE,
    ),
    IndexItem(
        name="value_from",
        label="HAS_VALUE",
        properties=["from"],
        type=IndexType.RANGE,
    ),
    IndexItem(
        name="value_branch",
        label="HAS_VALUE",
        properties=["branch"],
        type=IndexType.RANGE,
    ),
]
