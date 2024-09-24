from __future__ import annotations

from infrahub.database.constants import IndexType
from infrahub.database.index import IndexItem

node_indexes: list[IndexItem] = [
    IndexItem(name="node_uuid", label="Node", properties=["uuid"], type=IndexType.RANGE),
    IndexItem(name="node_kind", label="Node", properties=["kind"], type=IndexType.RANGE),
    IndexItem(name="attr_name", label="Attribute", properties=["name"], type=IndexType.RANGE),
    IndexItem(name="attr_uuid", label="Attribute", properties=["uuid"], type=IndexType.RANGE),
    IndexItem(name="attr_ipnet_bin", label="AttributeIPNetwork", properties=["binary_address"], type=IndexType.RANGE),
    IndexItem(name="attr_iphost_bin", label="AttributeIPHost", properties=["binary_address"], type=IndexType.RANGE),
    IndexItem(name="rel_uuid", label="Relationship", properties=["uuid"], type=IndexType.RANGE),
    IndexItem(name="rel_identifier", label="Relationship", properties=["name"], type=IndexType.RANGE),
]

rel_indexes: list[IndexItem] = [
    IndexItem(name="attr_from", label="HAS_ATTRIBUTE", properties=["from"], type=IndexType.RANGE),
    IndexItem(name="attr_branch", label="HAS_ATTRIBUTE", properties=["branch"], type=IndexType.RANGE),
    IndexItem(name="value_from", label="HAS_VALUE", properties=["from"], type=IndexType.RANGE),
    IndexItem(name="value_branch", label="HAS_VALUE", properties=["branch"], type=IndexType.RANGE),
]
